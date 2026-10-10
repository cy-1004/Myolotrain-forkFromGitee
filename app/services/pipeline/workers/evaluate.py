"""测试集评估（子进程）：python -m app.services.pipeline.workers.evaluate --weights best.pt --data dataset.yaml ..."""
import argparse
import json
import sys
import traceback


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--split", default="test")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--project", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    try:
        import torch
        from ultralytics import YOLO

        device = 0 if torch.cuda.is_available() else "cpu"
        model = YOLO(a.weights)
        res = model.val(data=a.data, split=a.split, imgsz=a.imgsz, batch=a.batch, device=device,
                        project=a.project, name="eval", exist_ok=True, plots=False, verbose=False, workers=0)
        names = model.names
        box = res.box
        per_class = {}
        # ap_class_index 是 numpy 数组，不能写成 `x or []`（数组的真值有歧义）
        raw_index = getattr(box, "ap_class_index", None)
        ap_class_index = [] if raw_index is None else [int(i) for i in raw_index]
        for i, cls_idx in enumerate(ap_class_index):
            per_class[names[int(cls_idx)]] = {
                "ap50_95": float(box.all_ap[i].mean()) if hasattr(box, "all_ap") else None,
                "ap50": float(box.all_ap[i][0]) if hasattr(box, "all_ap") else None,
            }
        out = {
            "split": a.split,
            "map50_95": float(box.map),
            "map50": float(box.map50),
            "precision": float(box.mp),
            "recall": float(box.mr),
            "per_class": per_class,
            "worst_class_ap50_95": min((v["ap50_95"] for v in per_class.values() if v["ap50_95"] is not None), default=None),
            "speed_ms": dict(res.speed) if hasattr(res, "speed") else None,
        }
    except Exception as e:
        traceback.print_exc()
        out = {"error": f"评估失败: {type(e).__name__}: {e}"}
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
