"""TFLite 导出与三道校验（子进程）

  1. 结构：能加载；输入 [1, imgsz, imgsz, 3] float32；输出 [1, 4+nc, N] 或其转置，nc 等于类别数；
  2. 数值：在真实测试图上逐元素对比 PT 与 TFLite 的原始输出（框坐标误差 px、类别分数误差）；
  3. 精度：PT 与 TFLite 在完整测试集上用**同一套** letterbox + NMS + 匹配算 mAP，比较下降量。
     两边必须走同一套后处理，否则下降量没有可比性（Ultralytics 自带 val 用的是 rect 推理，与端侧不同）。

python -m app.services.pipeline.workers.export_verify --weights best.pt --dataset-dir DIR --imgsz 640 --out-dir DIR --out report.json
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np

IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp")
IOUV = np.linspace(0.5, 0.95, 10)
CONF_THRES = 0.001
NMS_IOU = 0.7
MAX_DET = 300


def _list_images(dataset_dir: Path, split: str):
    d = dataset_dir / split / "images"
    return sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXTS) if d.exists() else []


def _load_gt(dataset_dir: Path, split: str, image: Path, w: int, h: int, imgsz: int):
    """读 YOLO 标签并换算到 letterbox 后的 imgsz 坐标系"""
    label = dataset_dir / split / "labels" / (image.stem + ".txt")
    boxes, classes = [], []
    if label.exists():
        for line in label.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            c, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:])
            boxes.append([(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h])
            classes.append(c)
    r = min(imgsz / h, imgsz / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    top, left = (imgsz - nh) // 2, (imgsz - nw) // 2
    b = np.array(boxes, dtype=np.float64).reshape(-1, 4)
    b[:, [0, 2]] = b[:, [0, 2]] * r + left
    b[:, [1, 3]] = b[:, [1, 3]] * r + top
    return b, np.array(classes, dtype=np.int64)


def _postprocess(raw: np.ndarray, nc: int):
    """原始输出 (1, 4+nc, N) -> (xyxy[K,4], conf[K], cls[K])，类别内 NMS"""
    import torch
    import torchvision

    pred = raw[0]
    if pred.shape[0] != 4 + nc and pred.shape[1] == 4 + nc:
        pred = pred.T
    xywh, scores = pred[:4].T, pred[4:].T
    conf = scores.max(1)
    cls = scores.argmax(1)
    keep = conf > CONF_THRES
    xywh, conf, cls = xywh[keep], conf[keep], cls[keep]
    if len(conf) == 0:
        return np.zeros((0, 4)), np.zeros(0), np.zeros(0, dtype=np.int64)
    xyxy = np.stack([xywh[:, 0] - xywh[:, 2] / 2, xywh[:, 1] - xywh[:, 3] / 2,
                     xywh[:, 0] + xywh[:, 2] / 2, xywh[:, 1] + xywh[:, 3] / 2], 1)
    idx = torchvision.ops.batched_nms(torch.from_numpy(xyxy).float(), torch.from_numpy(conf).float(),
                                      torch.from_numpy(cls), NMS_IOU)[:MAX_DET].numpy()
    return xyxy[idx], conf[idx], cls[idx]


def _box_iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.clip(br - tl, 0, None).prod(2)
    area_a = (a[:, 2:] - a[:, :2]).prod(1)
    area_b = (b[:, 2:] - b[:, :2]).prod(1)
    return inter / (area_a[:, None] + area_b[None, :] - inter + 1e-9)


def _match(pred_cls, true_cls, iou):
    """与 Ultralytics BaseValidator.match_predictions 相同的贪心匹配"""
    correct = np.zeros((len(pred_cls), len(IOUV)), dtype=bool)
    if len(pred_cls) == 0 or len(true_cls) == 0:
        return correct
    iou = iou * (true_cls[:, None] == pred_cls[None, :])
    for i, t in enumerate(IOUV):
        matches = np.array(np.nonzero(iou >= t)).T
        if matches.shape[0]:
            if matches.shape[0] > 1:
                matches = matches[iou[matches[:, 0], matches[:, 1]].argsort()[::-1]]
                matches = matches[np.unique(matches[:, 1], return_index=True)[1]]
                matches = matches[np.unique(matches[:, 0], return_index=True)[1]]
            correct[matches[:, 1].astype(int), i] = True
    return correct


def _map(stats, nc):
    from ultralytics.utils.metrics import ap_per_class

    if not stats:
        return None, None
    tp = np.concatenate([s[0] for s in stats])
    conf = np.concatenate([s[1] for s in stats])
    pcls = np.concatenate([s[2] for s in stats])
    tcls = np.concatenate([s[3] for s in stats])
    if len(tcls) == 0:
        return None, None
    if len(tp) == 0:
        return 0.0, 0.0
    ap = ap_per_class(tp, conf, pcls, tcls)[5]
    return float(ap.mean()), float(ap[:, 0].mean())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True)
    p.add_argument("--dataset-dir", required=True)
    p.add_argument("--imgsz", type=int, required=True)
    p.add_argument("--nc", type=int, required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--numeric-images", type=int, default=20)
    p.add_argument("--max-box-error-px", type=float, default=1.0)
    p.add_argument("--max-score-error", type=float, default=1e-3)
    p.add_argument("--max-map-drop", type=float, default=0.01)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    report = {"passed": False, "imgsz": a.imgsz, "gates": {}}
    work = tempfile.mkdtemp(prefix="export_verify_")
    try:
        from app.services import export_service
        from app.services.opencv_service import opencv_service
        import torch
        from ultralytics import YOLO

        out_dir = Path(a.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        exported = export_service.export_pt_to_tflite(a.weights, work, imgsz=a.imgsz)
        tflite_path = out_dir / "model_float32.tflite"
        shutil.copy2(exported, tflite_path)
        report["tflite_path"] = str(tflite_path)
        report["size_bytes"] = tflite_path.stat().st_size

        # ---- 关卡 1：结构 ----
        interpreter, inputs, outputs = export_service.load_tflite_interpreter(str(tflite_path))
        in_shape = [int(x) for x in inputs[0]["shape"]]
        out_shape = [int(x) for x in outputs[0]["shape"]]
        layout = None
        if len(out_shape) == 3 and out_shape[1] == 4 + a.nc:
            layout = "channels_first"   # [1, 4+nc, N]
        elif len(out_shape) == 3 and out_shape[2] == 4 + a.nc:
            layout = "channels_last"    # [1, N, 4+nc]
        # dtype 是 numpy 类型对象（str 后是 "<class 'numpy.float32'>"），要用 np.dtype 比较
        input_dtype = np.dtype(inputs[0]["dtype"])
        problems = []
        if in_shape != [1, a.imgsz, a.imgsz, 3]:
            problems.append(f"输入形状 {in_shape}，期望 [1, {a.imgsz}, {a.imgsz}, 3]")
        if input_dtype != np.float32:
            problems.append(f"输入类型 {input_dtype}，期望 float32")
        if layout is None:
            problems.append(f"输出形状 {out_shape}，期望 [1, {4 + a.nc}, N] 或 [1, N, {4 + a.nc}]")
        structure_ok = not problems
        report["gates"]["structure"] = {"passed": structure_ok, "input_shape": in_shape, "input_dtype": str(input_dtype),
                                        "output_shape": out_shape, "output_layout": layout, "nc": a.nc}
        if not structure_ok:
            report["error"] = "TFLite 结构不符合预期：" + "；".join(problems)
            return _finish(a.out, report, 1)

        # ---- 准备测试图（test 为空时退回 val） ----
        dataset_dir = Path(a.dataset_dir)
        split = "test" if _list_images(dataset_dir, "test") else "val"
        images = _list_images(dataset_dir, split)
        if not images:
            report["error"] = "测试集和验证集都没有图片，无法校验"
            return _finish(a.out, report, 1)

        torch_model = YOLO(a.weights).model.float().eval()
        box_err = score_err = 0.0
        latencies = []
        pt_stats, tfl_stats = [], []
        for i, image in enumerate(images):
            img = opencv_service.read_image(str(image))
            h, w = img.shape[:2]
            nhwc = export_service.letterbox(img, a.imgsz)
            nchw = np.transpose(nhwc, (0, 3, 1, 2)).copy()
            interpreter.set_tensor(inputs[0]["index"], nhwc.astype(inputs[0]["dtype"]))
            t0 = time.perf_counter()
            interpreter.invoke()
            latencies.append((time.perf_counter() - t0) * 1000)
            tfl_raw = interpreter.get_tensor(outputs[0]["index"])
            if layout == "channels_last":
                tfl_raw = tfl_raw.transpose(0, 2, 1)
            with torch.no_grad():
                out = torch_model(torch.from_numpy(nchw))
            pt_raw = (out[0] if isinstance(out, (list, tuple)) else out).cpu().numpy()

            if i < a.numeric_images:   # 关卡 2 只抽前 N 张
                diff = np.abs(pt_raw.astype(np.float64) - tfl_raw.astype(np.float64))
                box_err = max(box_err, float(diff[:, :4, :].max()))
                score_err = max(score_err, float(diff[:, 4:, :].max()))

            gt_boxes, gt_cls = _load_gt(dataset_dir, split, image, w, h, a.imgsz)
            for raw, stats in ((pt_raw, pt_stats), (tfl_raw, tfl_stats)):
                boxes, conf, cls = _postprocess(raw, a.nc)
                iou = _box_iou(gt_boxes, boxes) if len(gt_boxes) and len(boxes) else np.zeros((len(gt_boxes), len(boxes)))
                stats.append((_match(cls, gt_cls, iou), conf, cls, gt_cls))

        numeric_ok = box_err < a.max_box_error_px and score_err < a.max_score_error
        report["gates"]["numeric"] = {"passed": numeric_ok, "images": min(a.numeric_images, len(images)),
                                      "box_max_abs_error_px": box_err, "class_score_max_abs_error": score_err,
                                      "thresholds": {"box_px": a.max_box_error_px, "score": a.max_score_error}}

        # ---- 关卡 3：精度 ----
        pt_map, pt_map50 = _map(pt_stats, a.nc)
        tfl_map, tfl_map50 = _map(tfl_stats, a.nc)
        drop = (pt_map - tfl_map) if pt_map is not None and tfl_map is not None else None
        accuracy_ok = drop is not None and drop <= a.max_map_drop
        report["gates"]["accuracy"] = {"passed": accuracy_ok, "split": split, "images": len(images),
                                       "pt_map50_95": pt_map, "tflite_map50_95": tfl_map,
                                       "pt_map50": pt_map50, "tflite_map50": tfl_map50,
                                       "map50_95_drop": drop, "max_map_drop": a.max_map_drop,
                                       "postprocess": {"conf": CONF_THRES, "nms_iou": NMS_IOU, "max_det": MAX_DET}}
        report["cpu_latency_ms"] = {"mean": float(np.mean(latencies)), "p90": float(np.percentile(latencies, 90))}
        report["passed"] = structure_ok and numeric_ok and accuracy_ok
        if not report["passed"]:
            failed = [k for k, g in report["gates"].items() if not g["passed"]]
            report["error"] = f"TFLite 校验未通过：{', '.join(failed)}"
        return _finish(a.out, report, 0)
    except Exception as e:
        traceback.print_exc()
        report["error"] = f"TFLite 导出/校验出错: {type(e).__name__}: {e}"
        return _finish(a.out, report, 1)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _finish(path, report, code):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    return code


if __name__ == "__main__":
    sys.exit(main())
