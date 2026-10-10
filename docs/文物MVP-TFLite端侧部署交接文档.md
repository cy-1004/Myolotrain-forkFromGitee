# 文物识别MVP —— TFLite模型端侧部署交接文档

## 1. 模型概述

| 项目 | 说明 |
|---|---|
| 模型名称 | 文物mvp-v1 |
| 任务类型 | 目标检测（Object Detection） |
| 基础网络 | YOLO11n（Ultralytics） |
| 训练框架 | Ultralytics YOLO（PyTorch） |
| 源模型文件 | `文物mvp-v1_best.pt` |
| 交付格式 | `.tflite`（TensorFlow Lite） |
| 类别数 | 5 |

模型用于识别以下5类文物：

| class_id | 类别名（英文） | 说明（建议展示名） |
|---|---|---|
| 0 | JadeSeal | 玉玺/玉印 |
| 1 | JadeCup | 玉杯 |
| 2 | CalligraphyPaintings | 书画 |
| 3 | AncientCloth | 古代织物 |
| 4 | AncientBowl | 古碗 |

> 展示名请与业务/UI侧确认最终中文命名，上表为按数据集类别顺序给出的建议映射，**class_id的顺序不能变**，必须与训练时`dataset.yaml`中`names`列表的顺序完全一致。

---

## 2. TFLite模型是怎么来的（转换链路）

Android端使用的`.tflite`不是Ultralytics直接导出的，因为Ultralytics自带的TFLite导出依赖的LiteRT转换器只支持Linux x86和macOS，我们的训练/管理后端跑在Windows上，所以走的是：

```
文物mvp-v1_best.pt (PyTorch)
      │  ultralytics export(format=onnx, imgsz=640, opset=12)
      ▼
   中间ONNX模型
      │  onnx2tf（底层用TensorFlow自带的 tf.lite.TFLiteConverter）
      ▼
   文物mvp-v1.tflite（float32）
```

获取方式：在模型管理页面点击对应模型的 **TFLite** 按钮下载；后端接口为 `GET /api/models/{model_id}/download/tflite`。

下载前建议先点击同一行的 **验证** 按钮（对应接口 `POST /api/models/{model_id}/verify-tflite`），上传一张真实测试图片，确认：
- TFLite模型能正常加载、推理不报错；
- 和原始PT模型在同一张图上的检测目标数量、类别基本一致。

如果验证接口提示"PT与TFLite检测结果不一致"的警告，请先反馈给算法侧排查，不要直接把有问题的模型交给客户端。

---

## 3. 模型输入

| 属性 | 值 |
|---|---|
| 输入个数 | 1个张量 |
| 形状 | `[1, 640, 640, 3]`（NHWC：batch, height, width, channel） |
| 数据类型 | `float32` |
| 通道顺序 | RGB |
| 数值范围 | `[0.0, 1.0]`（像素值除以255归一化，**不是**ImageNet的均值方差标准化） |
| Batch | 固定为1，不支持动态batch |
| 输入尺寸 | 固定为640×640，**不支持**动态输入尺寸 |

### 3.1 预处理步骤（必须和训练/导出时保持一致，否则精度会明显下降）

Ultralytics在推理时对图片做的是 **letterbox（等比缩放+灰边填充）**，而不是直接拉伸到640×640。Android端必须复现同样的预处理逻辑：

1. 计算缩放比例 `scale = min(640 / img_width, 640 / img_height)`；
2. 按`scale`等比缩放原图；
3. 缩放后不足640×640的部分，用灰色（RGB均为114，即`(114,114,114)`，Ultralytics默认填充色）居中填充到640×640；
4. 转换通道顺序为RGB（Android Bitmap默认是ARGB，注意去掉alpha通道并调整通道顺序）；
5. 像素值除以255，转换为`float32`；
6. 按NHWC顺序写入输入`ByteBuffer`。

> 后续做坐标还原（第4节）时，需要记录第2、3步用到的`scale`和左右/上下填充的像素数（`pad_x`, `pad_y`），否则无法把模型输出的框坐标映射回原图坐标系。

---

## 4. 模型输出

### 4.1 重要提示：TFLite图里不包含NMS

Ultralytics导出的检测模型（无论ONNX还是TFLite）**默认只输出原始预测结果，不包含NMS（非极大值抑制）后处理**。也就是说，模型会对每一个候选框都输出结果，同一个目标周围可能有几十个重叠的框，NMS需要在Android端自己实现（或调用TFLite Support Library里现成的NMS工具类）。

### 4.2 输出张量

| 属性 | 值（以640输入、5类为例） |
|---|---|
| 输出个数 | 1个张量 |
| 形状 | `[1, 8400, 9]`（batch, num_anchors, 4+num_classes） |
| 数据类型 | `float32` |

- `8400` = 80×80 + 40×40 + 20×20，是640×640输入在stride 8/16/32三个检测层上的候选框（anchor point）总数，理论值，**请务必以实际拿到的`.tflite`文件为准去核实**（见4.4节）。
- `9` = 4（框坐标）+ 5（类别数）。

每一条预测（每个anchor）的9个值依次是：

| 索引 | 含义 |
|---|---|
| 0 | 框中心点 x（cx，单位：像素，相对于640×640输入图） |
| 1 | 框中心点 y（cy，单位：像素） |
| 2 | 框宽度 w（像素） |
| 3 | 框高度 h（像素） |
| 4 ~ 8 | 5个类别（JadeSeal / JadeCup / CalligraphyPaintings / AncientCloth / AncientBowl）各自的置信度分数，取值范围`[0,1]`，**已经过sigmoid激活**，不需要再手动做sigmoid |

> 注意：这里**没有单独的"目标置信度(objectness)"字段**，YOLO11沿用的是Ultralytics新版检测头设计，直接输出每个类别自己的置信度，取5个类别分数中的最大值作为该框的置信度、对应类别作为预测类别即可。

### 4.3 后处理流程（Android端需要实现）

1. **解析原始输出**：遍历8400个候选框，每个框取索引4~8共5个值，找最大值`max_score`和对应的`class_id`；
2. **置信度过滤**：丢弃`max_score`低于阈值（建议初始阈值`0.25`，可根据实测效果调整）的框；
3. **坐标转换**：`cx, cy, w, h` → `left, top, right, bottom`（`left = cx - w/2`，以此类推）；
4. **NMS**：按`class_id`分组，对每一组框按`max_score`降序做非极大值抑制，建议IoU阈值`0.45`；
5. **坐标还原到原图**：把NMS后剩余框的坐标，按第3.1节记录的`scale`、`pad_x`、`pad_y`做逆变换，换算回原始图片的像素坐标：
   ```
   original_x = (x_on_640 - pad_x) / scale
   original_y = (y_on_640 - pad_y) / scale
   ```
6. 用`class_id`查第1节的类别表得到类别名，用于展示。

### 4.4 如何核实真实的输入输出形状

模型每次更新都需要重新导出，anchor总数、张量名称等细节建议不要硬编码猜测，而是拿到实际的`.tflite`文件后用以下任一方式核实：

- **用Netron打开**（推荐，最直观）：https://netron.app ，导入`.tflite`文件，查看输入输出节点的shape和dtype；
- **调用后端验证接口**：`POST /api/models/{model_id}/verify-tflite`，返回JSON里的`input_shape`、`output_shape`字段就是用`tf.lite.Interpreter`实际读出来的真实形状；
- **Android本地调试**：加载模型后调用
  ```kotlin
  val inputShape = interpreter.getInputTensor(0).shape()
  val outputShape = interpreter.getOutputTensor(0).shape()
  ```
  打印出来确认。

---

## 5. Android集成建议

### 5.1 依赖

```gradle
implementation("org.tensorflow:tensorflow-lite:2.16.1")
implementation("org.tensorflow:tensorflow-lite-support:0.4.4") // 可选，提供ImageProcessor等工具类
implementation("org.tensorflow:tensorflow-lite-gpu:2.16.1")    // 可选，需要GPU加速时使用
```

版本号请与本次交付的`.tflite`是用哪个TensorFlow版本转换的对齐（转换端`requirements.txt`固定的是`tensorflow>=2.16.1`），如遇到`Interpreter`加载报算子不支持，优先尝试升级`tensorflow-lite`到更新的小版本。

### 5.2 加载与推理伪代码

```kotlin
// 1. 加载模型（放在assets目录）
val interpreter = Interpreter(loadModelFile(context, "wenwu_mvp_v1.tflite"))

// 2. 预处理：letterbox缩放 + 归一化，得到 640x640x3 的float32数组，按NHWC写入
val inputBuffer: ByteBuffer = preprocess(bitmap) // 见3.1节

// 3. 准备输出buffer，形状以interpreter.getOutputTensor(0).shape()为准
val outputBuffer = Array(1) { Array(numAnchors) { FloatArray(4 + numClasses) } }

// 4. 推理
interpreter.run(inputBuffer, outputBuffer)

// 5. 后处理：置信度过滤 + NMS + 坐标还原，见4.3节
val detections = postprocess(outputBuffer, scale, padX, padY)
```

### 5.3 性能相关

- 模型目前是**float32精度**，未做int8/float16量化，体积和耗时都是"未压缩"状态。如果Android端实测帧率不够、需要更快的实时推理，可以反馈给算法侧，让转换脚本（`onnx2tf.convert`）额外生成`float16`或`int8`量化版本，能显著减小体积、提升低端设备上的推理速度（int8量化通常还需要提供代表性数据集做校准，会牺牲一点精度，需要额外沟通）。
- 建议优先尝试开启**NNAPI Delegate**（`Interpreter.Options().setUseNNAPI(true)`）或**GPU Delegate**，在支持的设备上能明显提速；如果目标设备不支持，会自动回退到CPU执行。
- 真机测试前建议先用小流量做A/B验证，对比同一批图片在PT模型（服务端）和TFLite模型（端侧）上的检测结果差异，确认误检/漏检率在可接受范围内，而不是只看"能跑通"。

---

## 6. 已知限制 / 交接注意事项

1. **输入尺寸固定640×640，不支持动态尺寸**，也不支持除1以外的batch size。
2. **模型内部不含NMS**，必须在Android端自己实现4.3节的后处理逻辑，如果直接把原始8400个框全部渲染出来会看到大量重叠框，这是正常现象，不是模型坏了。
3. **预处理必须用letterbox**，如果偷懒直接resize拉伸到640×640（不保持宽高比），会导致长宽比失真、检测精度明显下降。
4. 当前交付的是**未量化的float32模型**，如果后续需要更小体积/更快速度的量化版本，需要额外走一次转换流程，请提前沟通。
5. 类别顺序、类别数如果后续训练数据集有变化（比如新增文物类别），`.tflite`需要重新导出，且第1节的class_id映射表要同步更新，务必以最新的`dataset.yaml`为准，不能沿用本文档旧版本的表格。
6. 每次拿到新的`.tflite`文件，建议先按4.4节的方式核实一遍真实的输入输出形状，不要假设和上一版完全一样。
