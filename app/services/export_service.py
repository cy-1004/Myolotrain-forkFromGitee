"""模型导出服务：PT -> ONNX -> TFLite，以及 PT/TFLite 输出一致性校验

从 app/api/endpoints/models.py 抽出，供下载接口、验证接口和后台流水线共用：
- 抛 ExportError 而不是 HTTPException，后台任务里也能调用；
- 输入尺寸 imgsz 参数化，默认取模型训练时的尺寸（TFLite 输入尺寸固定，必须与训练一致）；
- 导出结果持久化到 MODELS_DIR/exports/<模型ID>/，模型文件不变时重复下载直接复用，不再每次重新转换。

转换链路说明：Ultralytics 自带的 tflite 导出依赖 LiteRT 转换器，该转换器仅支持
Linux x86 和 macOS，在 Windows 上会直接报错。因此这里先导出 ONNX，再用 onnx2tf
（基于 TensorFlow 自带的 TFLiteConverter，跨平台可用）把 ONNX 转换为 TFLite。
Linux 容器里同样走这条链路，保证与端侧交接文档描述的产物一致。
"""
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.opencv_service import opencv_service

logger = logging.getLogger(__name__)

DEFAULT_IMGSZ = 640
ONNX_OPSET = 12


class ExportError(Exception):
    """导出或校验失败（消息可直接展示给用户）"""


def _import_tensorflow_cpu_only():
    """导入 TensorFlow 并禁止它使用 GPU

    TensorFlow 默认一初始化就占满整块显存。Linux 容器里训练进程和 Web 进程共用 GPU，
    导出时若让 TF 看到 GPU，正在进行的训练会被挤到显存不足。导出本来就在 CPU 上完成，
    所以必须在任何 TF 运算之前把 GPU 隐藏掉（已初始化过时设置会失败，此时只能保持现状）。
    """
    import tensorflow as tf

    try:
        tf.config.set_visible_devices([], "GPU")
    except (RuntimeError, ValueError):
        pass
    return tf


def get_model_imgsz(model_path: str) -> int:
    """读取模型训练时的输入尺寸；读不到时返回 DEFAULT_IMGSZ"""
    try:
        from ultralytics import YOLO

        args = getattr(YOLO(str(model_path)), "ckpt", None) or {}
        imgsz = (args.get("train_args") or {}).get("imgsz")
        if isinstance(imgsz, (list, tuple)):
            imgsz = max(imgsz)
        if isinstance(imgsz, int) and imgsz > 0:
            return imgsz
    except Exception as e:
        logger.warning(f"读取模型训练尺寸失败，使用默认值 {DEFAULT_IMGSZ}: {e}")
    return DEFAULT_IMGSZ


def export_pt_to_tflite(model_path: str, work_dir: str, imgsz: int = DEFAULT_IMGSZ) -> str:
    """将PT模型转换为TFLite，返回生成的 float32 .tflite 文件路径（位于 work_dir 内）"""
    from ultralytics import YOLO

    _import_tensorflow_cpu_only()
    try:
        import onnx2tf
    except ImportError:
        raise ExportError("TFLite模型转换失败: 缺少onnx2tf依赖，请先执行 pip install -r requirements.txt")

    # 第一步：加载PyTorch模型并导出为ONNX
    #
    # 注意：ultralytics 的 ONNX 导出会无视 project/name，把 .onnx 直接写在 .pt 文件旁边。
    # 直接用原始路径导出的话，中间产物会落在 app/static/models/ 下且永远不会被清理，
    # 每导出一次泄漏 ~10MB。所以先把 .pt 复制进 work_dir，从副本导出。
    pt_copy = os.path.join(work_dir, "source_model.pt")
    shutil.copy2(str(model_path), pt_copy)

    logger.info("正在加载YOLO模型...")
    yolo_model = YOLO(pt_copy)

    logger.info(f"开始导出中间ONNX模型（imgsz={imgsz}, opset={ONNX_OPSET}）...")
    onnx_path = yolo_model.export(
        format="onnx",
        imgsz=imgsz,
        opset=ONNX_OPSET,
        project=work_dir,
        name="onnx_export"
    )

    if not onnx_path or not os.path.exists(onnx_path):
        onnx_files = [os.path.join(root, f) for root, _, files in os.walk(work_dir) for f in files if f.endswith(".onnx")]
        if not onnx_files:
            raise ExportError("TFLite模型转换失败: 中间ONNX导出未生成任何文件")
        onnx_path = onnx_files[0]
    logger.info(f"中间ONNX模型导出成功: {onnx_path}")

    # 第二步：使用onnx2tf将ONNX转换为TFLite
    tflite_dir = os.path.join(work_dir, "tflite_export")
    logger.info("开始ONNX -> TFLite转换...")
    onnx2tf.convert(
        input_onnx_file_path=onnx_path,
        output_folder_path=tflite_dir,
        non_verbose=True,
    )

    # onnx2tf会生成多个精度版本，优先使用float32版本
    tflite_files = [os.path.join(root, f) for root, _, files in os.walk(tflite_dir) for f in files if f.endswith(".tflite")]
    if not tflite_files:
        raise ExportError("TFLite模型转换失败: 转换过程未生成任何TFLite文件")
    float32_files = [f for f in tflite_files if "float32" in os.path.basename(f)]
    tflite_path = float32_files[0] if float32_files else tflite_files[0]

    logger.info(f"TFLite模型导出成功: {tflite_path}（{os.path.getsize(tflite_path)} bytes）")
    return tflite_path


# ---------------------------------------------------------------------
# 导出结果持久化
# ---------------------------------------------------------------------

def _export_dir(model_id: str, imgsz: int) -> Path:
    return Path(settings.MODELS_DIR) / "exports" / str(model_id) / f"tflite_{imgsz}"


def _source_fingerprint(model_path: Path) -> Dict[str, Any]:
    stat = model_path.stat()
    return {"source_size": stat.st_size, "source_mtime": int(stat.st_mtime)}


def get_or_export_tflite(model_id: str, model_path: str, imgsz: Optional[int] = None) -> Tuple[Path, Dict[str, Any]]:
    """返回模型的 TFLite 文件，已有且源模型未变化时直接复用

    结果保存在 MODELS_DIR/exports/<模型ID>/tflite_<imgsz>/，旁边的 meta.json 记录源模型的
    大小和修改时间；源模型被替换后自动重新转换。

    Returns:
        (tflite 文件路径, meta 信息)
    """
    source = Path(model_path)
    if not source.exists():
        raise ExportError(f"模型文件不存在: {source}")
    imgsz = int(imgsz or get_model_imgsz(str(source)))

    out_dir = _export_dir(model_id, imgsz)
    tflite_file = out_dir / "model_float32.tflite"
    meta_file = out_dir / "meta.json"
    fingerprint = _source_fingerprint(source)

    if tflite_file.exists() and meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if all(meta.get(k) == v for k, v in fingerprint.items()):
                return tflite_file, meta
        except (OSError, ValueError):
            pass  # meta 损坏，重新导出

    work_dir = tempfile.mkdtemp(prefix="tflite_export_")
    try:
        exported = export_pt_to_tflite(str(source), work_dir, imgsz=imgsz)
        out_dir.mkdir(parents=True, exist_ok=True)
        # 先写临时文件再改名，避免并发下载读到写了一半的文件
        tmp_target = out_dir / f".model_float32.{os.getpid()}.tmp"
        shutil.copy2(exported, tmp_target)
        os.replace(tmp_target, tflite_file)
        meta = {
            "imgsz": imgsz,
            "precision": "float32",
            "onnx_opset": ONNX_OPSET,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            **fingerprint,
        }
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return tflite_file, meta
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------
# PT / TFLite 一致性校验
# ---------------------------------------------------------------------

def letterbox(img, size: int = DEFAULT_IMGSZ):
    """按 YOLO 的方式等比缩放 + 补边到 size x size，返回 float32 的 NHWC 张量 (1,size,size,3)"""
    import numpy as np
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = opencv_service.resize_image(img, nw, nh)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    # BGR -> RGB，归一化到 0~1
    rgb = canvas[:, :, ::-1].astype(np.float32) / 255.0
    return rgb[None]


def simple_nms(boxes, scores, iou_thr: float = 0.45) -> List[int]:
    """xyxy 上的标准 NMS，返回保留下来的下标"""
    import numpy as np
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_o = ((boxes[order[1:], 2] - boxes[order[1:], 0]) *
                  (boxes[order[1:], 3] - boxes[order[1:], 1]))
        iou = inter / (area_i + area_o - inter + 1e-9)
        order = order[1:][iou <= iou_thr]
    return keep


def postprocess_raw(raw, conf_thr: float = 0.25):
    """YOLO 原始输出 (1, 4+nc, N) -> (框数, 类别列表)"""
    import numpy as np
    pred = raw[0]
    xywh, cls_scores = pred[:4], pred[4:]
    best_cls = cls_scores.argmax(0)
    best_score = cls_scores.max(0)
    mask = best_score > conf_thr
    if not mask.any():
        return 0, []
    xy, wh = xywh[:2, mask], xywh[2:, mask]
    boxes = np.stack([xy[0] - wh[0] / 2, xy[1] - wh[1] / 2,
                      xy[0] + wh[0] / 2, xy[1] + wh[1] / 2], axis=1)
    scores, classes = best_score[mask], best_cls[mask]
    kept = []
    for ci in np.unique(classes):
        sel = classes == ci
        for _ in simple_nms(boxes[sel], scores[sel]):
            kept.append(int(ci))
    return len(kept), sorted(set(kept))


def run_tflite_and_compare(interpreter, input_details, output_details,
                           pt_model_path: str, image_path: str, imgsz: int = DEFAULT_IMGSZ):
    """用 TFLite 推理并与 PyTorch 原始输出逐元素比对

    返回 (检测框数, 类别列表, 数值误差报告)。
    数值误差是判断"转换有没有掉精度"最直接的证据 ——
    只比检测框个数的话，看不出误差量级到底是 1e-6 还是 1e-2。
    """
    import numpy as np
    import torch
    from ultralytics import YOLO

    img = opencv_service.read_image(image_path)
    nhwc = letterbox(img, imgsz)
    nchw = np.transpose(nhwc, (0, 3, 1, 2)).copy()

    # TFLite 前向
    interpreter.set_tensor(input_details[0]["index"], nhwc.astype(input_details[0]["dtype"]))
    interpreter.invoke()
    tfl_raw = interpreter.get_tensor(output_details[0]["index"])

    # PyTorch 前向（同一张预处理好的图，排除预处理差异）
    torch_model = YOLO(pt_model_path).model.float().eval()
    with torch.no_grad():
        out = torch_model(torch.from_numpy(nchw))
    pt_raw = (out[0] if isinstance(out, (list, tuple)) else out).cpu().numpy()

    if tfl_raw.shape != pt_raw.shape and tfl_raw.transpose(0, 2, 1).shape == pt_raw.shape:
        tfl_raw = tfl_raw.transpose(0, 2, 1)

    if tfl_raw.shape == pt_raw.shape:
        a = pt_raw.astype(np.float64)
        b = tfl_raw.astype(np.float64)
        diff = np.abs(a - b)
        numeric = {
            # 前 4 个通道是框坐标（像素），其余是各类别分数（0~1）
            "box_max_abs_error_px": float(diff[:, :4, :].max()),
            "class_score_max_abs_error": float(diff[:, 4:, :].max()),
            "overall_mean_abs_error": float(diff.mean()),
            "output_value_range": [float(a.min()), float(a.max())],
        }
    else:
        logger.warning("PT 与 TFLite 输出形状不一致: %s vs %s", pt_raw.shape, tfl_raw.shape)
        numeric = {"error": f"输出形状不一致: PT={pt_raw.shape}, TFLite={tfl_raw.shape}"}

    count, classes = postprocess_raw(tfl_raw)
    return count, classes, numeric


def load_tflite_interpreter(tflite_path: str):
    """加载 TFLite 模型，返回 (interpreter, input_details, output_details)"""
    tf = _import_tensorflow_cpu_only()
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()
    return interpreter, interpreter.get_input_details(), interpreter.get_output_details()
