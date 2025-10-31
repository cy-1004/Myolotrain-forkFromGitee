# Myolotrain - YOLO视觉模型训练平台

[![Gitee star](https://gitee.com/rock_kim/Myolotrain/badge/star.svg?theme=gvp)](https://gitee.com/rock_kim/Myolotrain/stargazers)
[![Gitee fork](https://gitee.com/rock_kim/Myolotrain//badge/fork.svg?theme=gvp)](https://gitee.com/rock_kim/Myolotrain/members)


Myolotrain是一个可视化管理yolo视觉模型训练的系统，为计算机视觉任务提供了直观的图形界面。该平台集成了数据集管理、模型管理、训练管理和目标检测功能，支持windows、linux、docker等多种部署方式，使用户能够轻松地训练和部署 YOLOv8 模型，支持CPU和GPU，使用tensorboard实时查看训练进度，具备数据集自动分割、数据集增强、实时检测、动态轨迹和预测等。

## 声明

- :construction:  **本项目目前处于早期开发阶段，现阶段功能并不完整，不建议用于生产环境，开发阶段API、功能和文档会频繁变动。欢迎参与开发、试用、提Issue 或提交PR。**

- :bangbang: **本项目独立开发的功能完全开源、不限制商用，因目前代码中的训练、推理等功能使用Ultralytics，具体开源协议请遵循Ultralytics，由于使用本项目而产生的商业纠纷或侵权行为一概与本项目开发者无关，请自行承担法律风险。**

- 自2025年10月后的代码，python版本须为3.12，目前此平台在python3.12，torch2.6.0、CUDA12.6环境下开发与测试，若您的环境无法安装以上版本，需自行解决numpy、onnxruntime等依赖版本问题（numpy版本对照：https://numpy.org/doc/  onnxruntime版本对照：https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)

## 致谢

感谢所有开发者的帮助与支持

### 更新日志：
<details>
<summary>-20251031  拆分main.js文件，增加多GPU/自动GPU训练，增加训练日志下载</summary>

> - 1.拆分main.js文件为多个js，包括在线标注、模型管理、训练管理、视频流、用户管理、视频管理等；
> - 2.新增多GPU训练，自动GPU训练功能；
> - 3.新增训练日志下载功能；
> - 4.修复继续训练检查点错误的问题；

</details>

<details>
<summary>-20251018  优化在线标注功能【开发者 @Tomle 贡献】</summary>

> - 1.调整高分辨率或浏览器有缩放的情况下，目标绘制框与十字标记错位问题；
> - 2.调整目标绘制完毕后主动退出编辑模式，无需再次点鼠标击标记框之外的位置
> - 3.调整绘制目标进入编辑模式的方法为三种：
> - 3.1点击左侧标注目标列表内的项目；
> - 3.2点击绘制目标左上角的文本标签；
> - 3.3.按住CTRL，鼠标点击绘制目标；
> - 4.调整绘制目标在编辑模式下鼠标的显示样式；

</details>

<details>
<summary>-20251015 优化在线标注功能，提高标注效率</summary>

> - 优化在线标注功能，增加辅助线、标注框选择与删除、增加标注框ID、鼠标滚轮放大缩小图片 。

</details>

<details>
<summary>-20251013 增加账户管理功能，优化提取帧功能</summary>

> - 开发者 @Tomle 完成：增加【用户管理】功能，初始账号密码admin/admin@123， **请手动更新依赖** 。
> - 优化视频处理-提取帧功能，增加下载、预览、删除服务器缓存功能
> - 更新依赖版本，删除onnxruntime（需手动安装），更新docker安装， **非docker用户需要手动安装onnxruntime，CPU版：onnxruntime>=1.21.0，GPU版：onnxruntime-gpu>=1.21.0** 并确保CUDA版本在12.0以上，python为3.12。

</details>


<details>
<summary>-20250903 更新ultralytics版本、解决手动中断任务继续训练日志监控的问题</summary>

> - ！！更新ultralytics 8.3.191，如tensorboard无法生成文件，请务必更新！手动更新亦可，同时手动启用tensorboard，命令行：yolo settings tensorboard=True
> - 解决手段中断训练任务后，点击继续训练新生成的日志无法展示的问题，修改为在原日志上继续写入
> - 解决已完成的训练任务重复轮询的问题

</details>

<details>
<summary>-20250901 修复数据集分割功能标签文件识别BUG</summary>

> - 修复数据集分割功能中，由于文件名称问题导致无法分割标签文件的BUG

</details>

<details>
<summary>-20250827 新增一级功能【在线标注】，解决提取帧问题</summary>

> - 新增一级功能【在线标注】主要功能：在线标注，支持w\s、a\d快捷键快速切换，利用现有模型自动标注（AI自动标注功能），一键导出标注信息（不包含原图片），导出为数据集（包含图片）等，具体介绍详见功能介绍板块
> - 临时解决视频处理->提取帧问题
> - 关闭视觉追踪模块

</details>

<details>
<summary>-20250825 新增流媒体，优化训练服务错误提示</summary>

> - 增加更多的日志捕获，解决训练状态异常问题
> - 视频处理->实时检测功能中新增流媒体功能，支持RTSP、RTMP、HTTP、摄像头

</details>

<details>
<summary>-20250513 增加华为昇腾NPU支持、增加新的目标追踪功能</summary>

> 关于昇腾NPU支持（仅支持linux部署使用）：
> - 通过torch_npu实现（深度学习框架依旧为pytorch，暂不支持MindSpore）
> - 需要手动安装：torch_npu（必须）、acl（必须）、onnxruntime-ascend（可选安装，后期扩展onnx格式数据集以及MindSpore架构）
> - torch_npu下载地址：https://gitee.com/ascend/pytorch/releases
> - 在新建训练任务选择设备类型“华为昇腾”并“获取昇腾信息”确认NPU信息获取无误后启动训练即可

</details>

### 注意事项 :exclamation:  :exclamation:  :exclamation: ：
 **（20250418）目前暂不支持yolov5，支持yolov8以上** 

 **（20250418）在根目录有yolov8n、yolov11n两个预训练模型，datasets_import下有测试数据集，供测试使用** 

**须手动安装torch环境（华为昇腾NPU环境请参考更新日志）**

如果torch相关依赖安装失败，请手动安装：

1、命令行安装(参考Pytorch官网)： https://pytorch.org/get-started/locally/

windwos环境示例：
```
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

2、手动下载地址：https://download.pytorch.org/whl/cu126 （cu126代表CUDA12.6）

手动请在下载whl时注意，torch-2.6.0+cu126-cp312-cp312-win_amd64.whl示意：2.6.0代表torch版本，cu126代表CUDA12.6版本，cp312代表pyhton3.12版本

 _此说明仅适用于GPU训练环境，如您为CPU环境，无需参考以上内容_ 

## 1. 功能介绍
### 1.1 技术特点

- **后端**：FastAPI框架，提供高性能的RESTful API
- **前端**：Bootstrap 5和现代JavaScript，提供响应式用户界面
- **数据库**：PostgreSQL，提供可靠的数据存储
- **模型引擎**：Ultralytics，提供先进的目标检测能力
- **可视化**：TensorBoard，提供实时训练监控和指标可视化

#### 1.1.1 主要特性

- **直观的Web界面**：基于FastAPI和现代前端技术构建的用户友好界面
- **多种数据集导入方式**：支持ZIP上传和服务器本地数据集
- **数据集分割**：支持自动分割数据集为训练集、验证集和测试集
- **灵活的训练配置**：支持矩形训练模式、GPU显存限制和多卡选择
- **GPU加速**：完整支持NVIDIA GPU加速训练
- **实时训练监控**：通过TensorBoard可视化训练过程和指标
- **模型测试**：内置图像和视频检测功能
- **多平台支持**：支持Windows、Linux和Docker部署
- **数据库集成**：使用 PostgreSQL 数据库存储数据集、模型和任务信息
- **异步处理**：支持长时间运行的训练和检测任务的异步处理
- **多用户支持**：支持多用户并发使用
- **可扩展性**：模块化设计，易于扩展新功能

### 1.2 核心功能

#### 1.2.1 在线标注

- **添加标注项目**：支持从系统数据集、本地上传图片压缩包（ZIP）自动解压（自动识别图片数量）、选择服务器目录方式导入需标注图片
- **AI自动标注**：支持通过已经上传到系统的模型进行自动标注，支持修改所标注模型的类别（不可修改顺序）
- **导出**：支持直接导出为系统数据集（可直接用于训练），导出标签文件（不带原图片）

**注意：扫描图片功能慎用，点击扫描图片后将清除所有标注！**

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E4%B8%BB%E7%95%8C%E9%9D%A2.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E6%A0%87%E6%B3%A8%E4%B8%BB%E7%95%8C%E9%9D%A2.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E7%BC%96%E8%BE%91%E7%B1%BB%E5%88%AB.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E8%87%AA%E5%8A%A8%E6%A0%87%E6%B3%A8.png)


#### 1.2.2 数据集管理
- **上传功能**：支持上传 YOLO 格式的数据集（ZIP 压缩包），自动解压并验证数据集结构 _（自动识别类别数量和图片数量及类别）_ 
- **直接导入功能**：支持在固定目录直接导入数据集文件，具备验证数据集结构功能 _（自动识别类别数量和图片数量及类别）_ 
- **分割功能**：支持对已上传的数据集进行比例分割，自动调整数据集内容
- **数据集列表**：查看所有上传的数据集，包括名称、描述、类别数量和图像数量
- **数据集详情**：查看数据集的详细信息，包括类别列表和示例图像
- **数据集删除**：删除不再需要的数据集，自动验证数据集是否被训练任务使用，如被使用则无法删除

![主页](%E4%BB%8B%E7%BB%8Dimages/%E4%B8%BB%E9%A1%B5.png)

![ZIP导入功能](%E4%BB%8B%E7%BB%8Dimages/%E4%B8%8A%E4%BC%A0ZIP.png)
ZIP导入功能

![目录导入功能](%E4%BB%8B%E7%BB%8Dimages/1.1%E4%BB%8E%E5%9B%BA%E5%AE%9A%E7%9B%AE%E5%BD%95%E5%AF%BC%E5%85%A5%E6%95%B0%E6%8D%AE%E9%9B%86%EF%BC%88%E9%9D%9E%E5%8E%8B%E7%BC%A9%E5%8C%85%E6%A0%BC%E5%BC%8F%EF%BC%89.png)

目录导入功能（非压缩格式）自动列出datasets_import下的所有目录名

![展示验证结果](%E4%BB%8B%E7%BB%8Dimages/1.3%E8%87%AA%E5%8A%A8%E9%AA%8C%E8%AF%81%E6%95%B0%E6%8D%AE%E9%9B%86%E5%86%85%E5%AE%B9%E5%8F%8A%E7%B1%BB%E5%88%AB.png)

展示验证结果

![数据集分割](%E4%BB%8B%E7%BB%8Dimages/1.4%E4%B8%A4%E7%A7%8D%E5%88%86%E5%89%B2%E6%A8%A1%E5%BC%8F.png)

数据集分割

![具备两种分割模式](%E4%BB%8B%E7%BB%8Dimages/1.2%E5%88%86%E5%89%B2%E6%95%B0%E6%8D%AE%E9%9B%86.png)

具备两种分割模式

#### 1.2.3 模型管理
- **上传功能**：支持上传预训练的 YOLO模型以及训练后的模型（.pt 文件）
- **模型列表**：查看所有可用的模型，包括预训练模型和训练生成的模型
- **模型详情**：查看模型的详细信息，包括模型类型、任务类型和来源
- **模型删除**：删除不再需要的模型，自动验证模型是否正在被训练任务使用，如被使用则无法删除
![模型管理](%E4%BB%8B%E7%BB%8Dimages/2%E6%A8%A1%E5%9E%8B%E7%AE%A1%E7%90%86.png)

#### 1.2.4 训练管理
- **创建训练任务**：选择数据集、预训练模型和训练参数
- **训练参数配置**：配置批次大小、学习率、训练轮数和图像大小等参数
- **硬件资源配置**：配置 CPU、GPU 和内存使用限制
- **训练监控**：实时监控训练进度，包括损失曲线和指标
- **TensorBoard 集成**：通过 TensorBoard 可视化训练过程
- **训练管理**：查看、暂停和取消训练任务

![训练任务](%E4%BB%8B%E7%BB%8Dimages/3%E8%AE%AD%E7%BB%83%E4%BB%BB%E5%8A%A1.png)

![GPU显存控制](%E4%BB%8B%E7%BB%8Dimages/GPU%E6%98%BE%E5%AD%98%E6%8E%A7%E5%88%B6.png)

![tensorboard](%E4%BB%8B%E7%BB%8Dimages/tensorboard.png)


#### 1.2.5 模型测试功能
- **图像检测**：上传图像并使用选定的模型进行目标检测
- **视频检测**：上传视频并使用选定的模型进行目标检测
- **检测参数配置**：配置置信度阈值、IoU 阈值和类别过滤等参数
- **结果可视化**：显示检测结果，包括边界框、类别标签和置信度
- **结果下载**：下载检测结果图像或视频
![模型验证](%E4%BB%8B%E7%BB%8Dimages/4%E9%AA%8C%E8%AF%81%E5%8A%9F%E8%83%BD.png)

![验证结果](%E4%BB%8B%E7%BB%8Dimages/%E9%AA%8C%E8%AF%81%E6%95%88%E6%9E%9C.png)

#### 1.2.6 图像处理功能
- **图像预处理**：可以调整大小、去噪、亮度和对比度、锐化
- **图像分析**：上传图像进行质量分析
- **数据增强** ：可倍数扩展数据集图片，具备水平和垂直翻转、旋转、添加噪声、亮度和对比度变化、透视变换功能

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E5%9B%BE%E5%83%8F%E5%A4%84%E7%90%86.png)

#### 1.2.7 视频处理功能
- **提取帧**：上传视频并按照指定间隔提取帧。
- **场景检测**：上传视频进行场景变化检测。
- **运动检测**：上传视频进行运动检测。
- **实时检测**：使用模型对视频或摄像头进行实时目标检测。具备报警区域绘制、报警项目自定义、运动轨迹追踪、运动轨迹预测等功能。

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E6%91%84%E5%83%8F%E5%A4%B4%E6%88%96%E8%A7%86%E9%A2%91.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E5%A4%9A%E7%9B%AE%E6%A0%87%E6%8A%A5%E8%AD%A6.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E6%8A%A5%E8%AD%A6.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E6%8A%A5%E8%AD%A6%E5%8E%86%E5%8F%B2.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E8%BD%A8%E8%BF%B9%E5%92%8C%E9%A2%84%E6%B5%8B2.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/%E8%BD%A8%E8%BF%B9%E5%92%8C%E9%A2%84%E6%B5%8B.png)

#### 1.2.8 目标追踪(20250827功能暂时关闭）

技术实现流程：

1、**输入处理**：从摄像头获取视频帧，使用YOLO模型进行目标检测

2、**特征提取**：裁剪检测到的目标区域、使用带有CBAM的特征提取器提取特征的Transformer编码器增强特征

3、**目标匹配**：预测轨迹的下一个位置、使用交叉注意力计算当前检测与现有轨迹的相似度、结合IOU和特征相似度进行匹配

4、**轨迹更新**：更新匹配的轨迹、创建新的轨迹、管理未匹配的轨迹

5、**结果可视化**：绘制检测框和追踪框、显示目标ID和类别、绘制运动轨迹



![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/transformer%E8%BF%BD%E8%B8%AA.png)

![输入图片说明](%E4%BB%8B%E7%BB%8Dimages/transformer%E5%8D%95%E7%9B%AE%E6%A0%87%E8%BF%BD%E8%B8%AA.png)

## 2 目录结构

```
Myolotrain/
├── app/                        # 应用程序代码
│   ├── api/                    # API 端点
│   │   ├── endpoints/          # API 路由处理函数
│   │   └── api.py              # API 路由注册
│   ├── core/                   # 核心配置
│   │   └── config.py           # 应用程序配置
│   ├── crud/                   # 数据库 CRUD 操作
│   │   ├── crud_dataset.py     # 数据集 CRUD
│   │   ├── crud_model.py       # 模型 CRUD
│   │   ├── crud_training.py    # 训练任务 CRUD
│   │   └── crud_detection_task.py# 检测任务 CRUD
│   ├── db/                     # 数据库连接
│   │   ├── init_db.py          # 数据库初始化
│   │   └── session.py          # 数据库会话
│   ├── models/                 # 数据库模型
│   │   ├── dataset.py          # 数据集模型
│   │   ├── model.py            # 模型模型
│   │   ├── training_task.py    # 训练任务模型
│   │   └── detection_task.py   # 检测任务模型
│   ├── patches/                # 环境文件
│   │   ├── torch_load_path.py  # torch导入环境
│   ├── schemas/                # Pydantic 模式
│   │   ├── dataset.py          # 数据集模式
│   │   ├── model.py            # 模型模式
│   │   ├── training.py         # 训练任务模式
│   │   └── detection.py        # 检测任务模式
│   ├── services/               # 业务逻辑
│   │   ├── dataset_service.py  # 数据集服务
│   │   ├── model_service.py    # 模型服务
│   │   ├── training_service.py # 训练服务
│   │   ├── detection_service.py# 检测服务
│   │   ├── process_monitor.py  # 进程监控服务
│   │   └── tensorboard_service.py # TensorBoard 服务
│   │   └── upload_service.py   # 上传服务
│   ├── static/                 # 静态文件
│   │   ├── css/                # CSS 样式
│   │   ├── js/                 # JavaScript 脚本
│   │   ├── uploads/            # 上传文件临时存储
│   │   ├── datasets/           # 数据集存储
│   │   ├── models/             # 模型存储（  :star: 训练生成的所有文件存储，包括模型文件）
│   │   └── results/            # 检测结果存储
│   └── main.py                 # 应用程序入口点
├── logs/                       # 日志文件
│   └── tensorboard/            # TensorBoard 日志（ :star: 训练过程日志）
├── datasets_import/            # 数据集导入目录（存在这里的数据集可以通过文件导入，不需要压缩）
├── config.yaml                 # 配置文件
├── create_example_dataset.py   # 创建示例数据集脚本
├── dataset.py                  # 数据集处理脚本
├── detect.py                   # 检测脚本
├── docker-compose.yml          # Docker Compose 配置
├── Dockerfile                  # Docker 配置
├── init_db.py                  # 数据库初始化脚本
├── README.md                   # 项目说明
├── requirements.txt            # 依赖项
├── run.py                      # 运行脚本（主程序运行脚本）
├── setup_venv.bat              # Windows 虚拟环境设置脚本
├── setup_venv.py               # 虚拟环境设置脚本
├── setup_venv.sh               # Linux 虚拟环境设置脚本
├── start.py                    # 启动脚本（ :boom: 此启动脚本作为初始化功能，会重置数据库，请谨慎操作）
└── train.py                    # 训练脚本（独立的训练脚本）
```



## 3 系统要求

- **操作系统**：Windows 10/11、Linux（Ubuntu 18.04+）或macOS
- **Python**：Python 3.12或更高版本
- **数据库**：PostgreSQL 12或更高版本
- **硬件**：
  - CPU：建议4核心以上
  - 内存：建议8GB RAM以上
  - 存储：至少10GB可用空间
  - GPU：支持CUDA的NVIDIA GPU（推荐，但不是必需）

## 4 快速开始

### 4.1 Windows安装（推荐）

1. **安装PostgreSQL**
   - 从[PostgreSQL官网](https://www.postgresql.org/download/windows/)下载并安装PostgreSQL
   - 安装过程中设置用户名为`postgres`，密码为`postgres`
   - 确保PostgreSQL服务已启动

- **操作系统**：Windows 10/11、Linux（Ubuntu 18.04+）或 macOS
- **Python**：Python 3.12
- **数据库**：PostgreSQL 12 或更高版本
- **硬件**：
  - CPU：建议 4 核心以上
  - 内存：建议 8GB RAM以上
  - 存储：至少 10GB 可用空间
  - GPU：支持 CUDA 的 NVIDIA GPU（推荐，但不是必需）


2. **安装Python**
   - 从[Python官网](https://www.python.org/downloads/)下载并安装Python 3.12或更高版本
   - 安装时勾选"Add Python to PATH"选项

3. **获取项目**
   - 使用Git克隆项目或下载项目压缩包并解压
   ```
   git clone https://gitee.com/rock_kim/Myolotrain.git
   cd Myolotrain
   ```

4. **启动系统**
   - 使用管理员权限运行`启动.bat`
   - 注意：请保持命令窗口打开，否则系统将停止运行

5. **访问系统**
   - 打开浏览器访问 http://localhost:8000

### 4.2 Docker部署

1. 从 [Python 官网](https://www.python.org/downloads/) 下载并安装 Python 3.12
2. 安装时勾选"Add Python to PATH"选项


1. **安装Docker和Docker Compose**
   - 安装[Docker](https://docs.docker.com/get-docker/)
   - 安装[Docker Compose](https://docs.docker.com/compose/install/)

2. **CPU版本部署**
   ```bash
   docker-compose up -d
   ```

3. **GPU版本部署**
   - 确保已安装[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
   ```bash
   docker-compose -f docker-compose-gpu.yml up -d
   ```

4. **访问系统**
   - Web界面: http://localhost:8000
   - TensorBoard: http://localhost:6006

## 5 GPU设置

本项目支持使用NVIDIA GPU加速训练过程。默认配置适用于CUDA 12.6，如果您使用不同版本的CUDA，请按照以下步骤操作：

### 5.1 CUDA 12.6设置（默认）

如果torch相关依赖安装失败，请手动安装：

```bash
# Windows环境示例
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

### 5.2 其他CUDA版本

如果您使用其他CUDA版本，请根据您的版本安装对应的PyTorch：

1. 访问[PyTorch官网](https://pytorch.org/get-started/locally/)选择适合您CUDA版本的安装命令
2. 手动下载对应版本的whl文件进行安装

### 5.3 验证GPU设置

使用以下Python代码验证PyTorch是否能够检测到GPU：

```python
import torch

print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA是否可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA版本: {torch.version.cuda}")
    print(f"GPU数量: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
```

1. 安装 Python 和开发工具
   ```
   sudo apt install python3.12 python3.12-dev python3.12-venv python3-pip
   ```


## 6 使用指南

### 6.1 数据集管理

#### 6.1.1 数据集准备

准备YOLO格式的数据集，目录结构如下：

```
dataset/
├── classes.txt           # 类别名称文件
├── train/
│   ├── images/           # 训练图像
│   └── labels/           # 训练标签
├── val/
│   ├── images/           # 验证图像
│   └── labels/           # 验证标签
└── test/                 # 可选
    ├── images/           # 测试图像
    └── labels/           # 测试标签
```

#### 6.1.2 数据集导入方式

- **ZIP上传**：将数据集打包为ZIP文件，在Web界面中点击"添加数据集"上传
- **服务器数据集**：点击"服务器数据集"按钮，选择服务器上的数据集文件夹，可选择是否验证

#### 6.1.3 数据集分割

系统支持将数据集自动分割为训练集、验证集和测试集：

1. 在数据集列表页面选择"分割数据集"
2. 设置训练集、验证集和测试集的比例
3. 点击"确定"执行分割

### 6.2 模型管理

- **上传模型**：支持上传预训练的YOLOv8模型（.pt文件）
- **模型列表**：查看所有可用的模型，包括预训练模型和训练生成的模型
- **模型详情**：查看模型的详细信息，包括模型类型、任务类型和来源

### 6.3 训练管理

#### 6.3.1 创建训练任务

1. 在Web界面中点击"创建训练任务"
2. 选择数据集和预训练模型（可选）
3. 设置训练参数：
   - 批次大小、学习率、训练轮数
   - 图像大小（支持矩形训练模式）
   - 硬件资源配置（CPU/GPU、内存限制）
4. 点击"开始训练"

#### 6.3.2 训练监控

- 实时监控训练进度，包括损失曲线和指标
- 通过TensorBoard可视化训练过程
- 查看、暂停和取消训练任务

### 6.4 模型测试

- **图像检测**：上传图像并使用选定的模型进行目标检测
- **视频检测**：上传视频并使用选定的模型进行目标检测
- **检测参数配置**：配置置信度阈值、IoU阈值和类别过滤等参数
- **结果可视化**：显示检测结果，包括边界框、类别标签和置信度
- **结果下载**：下载检测结果图像或视频

## 7 注意事项

1. **数据集格式**：
   - 上传数据集建议使用classes.txt格式，每个类别名称一行
   - 必须有yaml或者classes.txt文件，如果没有yaml文件，系统会根据classes.txt自动生成
   - 压缩为zip格式，并确保文件在根目录（不得有高一层的总目录）

2. **图像尺寸**：
   - 图片尺寸尽量一致，建议为640×640（YOLO官方默认尺寸）
   - 如果使用非固定比例图像，请选择"矩形训练模式"并输入图片长宽
   - 考虑训练步长问题，建议宽为8的倍数

3. **预训练模型**：
   - 建议自行下载预训练模型，如果没有系统将自动下载，但速度较慢

4. **GPU训练**：
   - 确保已正确安装CUDA和PyTorch
   - 如遇到内存不足错误，可减小批量大小或设置合理的GPU显存限制

## 8 故障排除

### 8.1 数据库连接问题

- 确保PostgreSQL服务正在运行
- 检查数据库连接参数是否正确
- 尝试手动连接数据库以验证凭据
- 修改配置文件以调整数据库连接参数主要是两个文件，`config.py`和`init_db.py`
### 8.2 模型训练问题

- 检查数据集格式是否正确
- 确保有足够的磁盘空间和内存
- 查看训练日志以获取详细错误信息

### 8.3 Web服务器问题

- 检查端口8000是否被占用
- 确保已安装所有依赖项
- 查看应用程序日志以获取详细错误信息

### 8.4 TensorBoard问题

- 检查端口6006是否被占用
- 确保TensorBoard已正确安装
- 尝试手动启动TensorBoard以验证配置


## 9 未来计划



## 10 贡献

欢迎贡献代码、报告问题或提出改进建议。请通过以下方式参与项目：

1. Fork项目
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开Pull Request

## 11 许可证

本项目采用AGPL-3.0 协议许可证 - 详情请参见LICENSE文件

## 12 知识产权声明
1. 训练功能依赖 [Ultralytics YOLOv8/v11](https://github.com/ultralytics/ultralytics)，其使用 **AGPL-3.0 协议**  
2. 本平台不承担用户违反第三方协议的责任  