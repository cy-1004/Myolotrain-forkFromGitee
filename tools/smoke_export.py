"""TFLite 转换链路冒烟测试：PT -> ONNX -> TFLite，并校验输入输出形状和数值误差

用途：升级 torch / TensorFlow / onnx2tf / ultralytics 任何一个之后，或构建新镜像后，跑一遍确认导出仍然可用。

    python tools/smoke_export.py                     # 默认 WEIGHTS_DIR 下的 yolo11n.pt，imgsz=320（更快）
    python tools/smoke_export.py --weights x.pt --imgsz 640
    docker compose exec app python tools/smoke_export.py

退出码 0 = 通过，1 = 失败。只在临时目录里工作，不写数据库、不留文件。
"""
import argparse
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数值误差阈值：float32 转换后应基本无损，与 v2 设计文档"三道校验"的数值关卡一致
MAX_BOX_ERROR_PX = 1.0
MAX_SCORE_ERROR = 1e-3


def main() -> int:
    from app.core.config import settings
    from app.services import export_service

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weights", default=str(settings.WEIGHTS_DIR / "yolo11n.pt"))
    parser.add_argument("--imgsz", type=int, default=320)
    args = parser.parse_args()

    if not os.path.exists(args.weights):
        print(f"[FAIL] 权重文件不存在: {args.weights}")
        return 1

    import numpy as np
    from PIL import Image

    work_dir = tempfile.mkdtemp(prefix="smoke_export_")
    started = time.time()
    try:
        tflite_path = export_service.export_pt_to_tflite(args.weights, work_dir, imgsz=args.imgsz)
        interpreter, inputs, outputs = export_service.load_tflite_interpreter(tflite_path)

        in_shape = [int(x) for x in inputs[0]["shape"]]
        out_shape = [int(x) for x in outputs[0]["shape"]]
        print(f"TFLite: {tflite_path}（{os.path.getsize(tflite_path) / 1e6:.1f} MB）")
        print(f"输入形状 {in_shape}，输出形状 {out_shape}")

        failures = []
        if in_shape != [1, args.imgsz, args.imgsz, 3]:
            failures.append(f"输入形状应为 [1, {args.imgsz}, {args.imgsz}, 3]")

        # 用一张有内容的合成图（渐变 + 色块），纯噪声图上模型输出全接近 0，误差比较没有意义
        h = w = args.imgsz
        grad = np.linspace(0, 255, w, dtype=np.uint8)
        img = np.stack([np.tile(grad, (h, 1)), np.tile(grad[::-1], (h, 1)), np.full((h, w), 128, np.uint8)], axis=2)
        img[h // 4:h // 2, w // 4:w // 2] = (220, 40, 40)
        image_path = os.path.join(work_dir, "probe.jpg")
        Image.fromarray(img).save(image_path)

        _, _, numeric = export_service.run_tflite_and_compare(
            interpreter, inputs, outputs, args.weights, image_path, imgsz=args.imgsz)
        print(f"数值误差: {numeric}")
        if "error" in numeric:
            failures.append(numeric["error"])
        else:
            if numeric["box_max_abs_error_px"] >= MAX_BOX_ERROR_PX:
                failures.append(f"框坐标最大误差 {numeric['box_max_abs_error_px']:.4f}px ≥ {MAX_BOX_ERROR_PX}px")
            if numeric["class_score_max_abs_error"] >= MAX_SCORE_ERROR:
                failures.append(f"类别分数最大误差 {numeric['class_score_max_abs_error']:.2e} ≥ {MAX_SCORE_ERROR}")

        elapsed = time.time() - started
        if failures:
            for f in failures:
                print(f"[FAIL] {f}")
            return 1
        print(f"[PASS] TFLite 转换链路正常（{elapsed:.0f}s）")
        return 0
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        return 1
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
