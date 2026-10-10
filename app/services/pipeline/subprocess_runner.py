"""在子进程中执行重活（评估、TFLite 导出校验）

放到子进程而不是 Web 进程里：
- TensorFlow 一旦在进程内初始化就常驻内存，还可能占住 GPU；
- 评估/导出出现原生库崩溃（段错误等）时只影响这一个子进程，Web 服务和其他 Run 不受影响；
- 可以随时杀掉（取消 Run、超时）。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.services.pipeline.errors import PipelineError, RunCancelled


def run_worker(ctx, module: str, args: List[str], *, out_json: Path, log_path: Path, error_code: str,
               timeout_seconds: int = 3600, cpu_only: bool = False, progress_hint: Optional[str] = None) -> Dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = str(settings.BASE_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    if cpu_only:
        env["CUDA_VISIBLE_DEVICES"] = ""   # 导出/校验不需要 GPU，避免 TensorFlow 抢占显存
    out_json.parent.mkdir(parents=True, exist_ok=True)
    if out_json.exists():
        out_json.unlink()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with open(log_path, "a", encoding="utf-8", errors="replace") as log:
        log.write(f"\n===== {module} {' '.join(args)} =====\n")
        log.flush()
        proc = subprocess.Popen([sys.executable, "-m", module, *args, "--out", str(out_json)],
                                stdout=log, stderr=subprocess.STDOUT, cwd=str(settings.BASE_DIR), env=env)
        try:
            while proc.poll() is None:
                try:
                    ctx.check_cancel()
                except RunCancelled:
                    proc.kill()
                    raise
                elapsed = time.monotonic() - started
                if elapsed > timeout_seconds:
                    proc.kill()
                    raise PipelineError(error_code, f"{progress_hint or module} 超时（{timeout_seconds}s）")
                ctx.progress(min(0.95, elapsed / max(60.0, timeout_seconds / 10)), detail={"step": progress_hint})
                time.sleep(2)
        finally:
            if proc.poll() is None:
                proc.kill()
    result = None
    if out_json.exists():
        try:
            result = json.loads(out_json.read_text(encoding="utf-8"))
        except ValueError:
            result = None
    if proc.returncode != 0 or result is None:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:] if log_path.exists() else ""
        message = (result or {}).get("error") if isinstance(result, dict) else None
        raise PipelineError(error_code, message or f"{progress_hint or module} 失败（退出码 {proc.returncode}）",
                            details={"log_tail": tail})
    return result
