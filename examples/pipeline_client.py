"""对外接口调用示例：上传视频 → 创建一键训练任务 → 轮询进度 → 下载交付包

    python examples/pipeline_client.py --base http://127.0.0.1:8000 --key myo_sk_xxx \\
        --video JadeCup=jade_cup_01.mp4 --video JadeCup=jade_cup_02.mp4 --video AncientBowl=bowl_01.mp4 \\
        --video JadeCup+AncientBowl=desk_01.mp4 --reference JadeCup=cup_photo.jpg \\
        --name 文物批次-2026-10 --out ./delivery

--video 格式为 <类别名>=<视频路径>；一个视频里有几类文物时用 + 连接类别名。
--reference 格式为 <类别名>=<图片路径>，该文物的清晰照片（可选，每类最多 3 张，强烈建议提供）。
大于 --chunk-threshold-mb 的视频走分片上传，其余随建任务的 multipart 请求一起上传。
只依赖 httpx（pip install httpx）。
"""
import argparse
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

CHUNK = 8 * 1024 * 1024


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def check(resp: httpx.Response):
    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {})
        except ValueError:
            err = {"message": resp.text}
        raise SystemExit(f"HTTP {resp.status_code} {err.get('code')}: {err.get('message')} {err.get('details') or ''}")
    return resp.json()


def chunked_upload(client: httpx.Client, path: Path) -> str:
    size = path.stat().st_size
    up = check(client.post("/api/v1/uploads", json={"filename": path.name, "size": size, "sha256": sha256_of(path)}))
    upload_id, chunk = up["upload_id"], up["chunk_size"]
    with open(path, "rb") as f:
        offset = 0
        while offset < size:
            f.seek(offset)
            data = f.read(chunk)
            end = offset + len(data) - 1
            resp = client.put(f"/api/v1/uploads/{upload_id}", content=data,
                              headers={"Content-Range": f"bytes {offset}-{end}/{size}"})
            if resp.status_code == 409:   # 断点续传：以服务端已接收的字节数为准
                offset = resp.json()["error"]["details"]["received"]
                continue
            offset = check(resp)["received"]
            print(f"  {path.name}: {offset * 100 // size}%", end="\r")
    check(client.post(f"/api/v1/uploads/{upload_id}/complete"))
    print(f"  {path.name}: 上传完成        ")
    return upload_id


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--key", required=True)
    p.add_argument("--video", action="append", required=True, help="<类别名>[+<类别名>…]=<视频路径>，可多次指定")
    p.add_argument("--reference", action="append", default=[], help="<类别名>=<参考图路径>，可多次指定")
    p.add_argument("--name", default="pipeline-job")
    p.add_argument("--review-mode", default="on_anomaly", choices=["auto", "on_anomaly", "full"])
    p.add_argument("--config", help="任务 config 的 JSON（可选，覆盖默认的切帧/标注/训练参数）")
    p.add_argument("--callback-url")
    p.add_argument("--chunk-threshold-mb", type=float, default=64)
    p.add_argument("--out", default="./delivery")
    p.add_argument("--no-wait", action="store_true")
    a = p.parse_args()

    videos = []
    for i, item in enumerate(a.video, 1):
        cls, _, path = item.partition("=")
        if not path:
            raise SystemExit(f"--video 格式应为 <类别名>=<视频路径>: {item}")
        videos.append({"key": f"v{i}", "classes": cls.split("+"), "path": Path(path)})
    classes = sorted({c for v in videos for c in v["classes"]})
    refs = {}
    for item in a.reference:
        cls, _, path = item.partition("=")
        if cls not in classes or not path:
            raise SystemExit(f"--reference 格式应为 <类别名>=<图片路径>，类别须出现在 --video 中: {item}")
        refs.setdefault(cls, []).append(Path(path))
    spec = {"name": a.name, "review_mode": a.review_mode,
            "classes": [{"name": c, **({"references": [{"file": p.name} for p in refs[c]]} if c in refs else {})}
                        for c in classes],
            "videos": [{"key": v["key"], **({"class": v["classes"][0]} if len(v["classes"]) == 1 else {"classes": v["classes"]})}
                       for v in videos]}
    if a.config:
        spec["config"] = json.loads(a.config)
    if a.callback_url:
        spec["callback_url"] = a.callback_url

    headers = {"X-API-Key": a.key, "Idempotency-Key": uuid.uuid4().hex}
    with httpx.Client(base_url=a.base, headers=headers, timeout=httpx.Timeout(600, connect=10), trust_env=False) as client:
        big = [v for v in videos if v["path"].stat().st_size > a.chunk_threshold_mb * 1024 * 1024]
        small = [v for v in videos if v not in big]
        for v in big:
            sv = next(s for s in spec["videos"] if s["key"] == v["key"])
            sv["upload_id"] = chunked_upload(client, v["path"])
        if small or refs or not big:
            files = [("videos", (v["path"].name, open(v["path"], "rb"), "application/octet-stream")) for v in small]
            files += [("references", (p.name, open(p, "rb"), "image/jpeg")) for ps in refs.values() for p in ps]
            for v in small:
                next(s for s in spec["videos"] if s["key"] == v["key"])["file"] = v["path"].name
            job = check(client.post("/api/v1/pipeline/jobs", data={"spec": json.dumps(spec, ensure_ascii=False)}, files=files))
        else:
            job = check(client.post("/api/v1/pipeline/jobs", json=spec))
        job_id = job["job_id"]
        print(f"任务已创建: {job_id}")
        if a.no_wait:
            return

        after, last_line = 0, ""
        while True:
            events = check(client.get(f"/api/v1/pipeline/jobs/{job_id}/events", params={"after": after}))
            for e in events["items"]:
                print(f"[{e['ts']}] {e['level']:7s} {e['type']}: {e['message']}")
            after = events["next_after"]
            job = check(client.get(f"/api/v1/pipeline/jobs/{job_id}"))
            line = f"状态 {job['status']}  阶段 {job['stage']}  整体进度 {job['progress']['overall']:.0%}"
            if line != last_line:
                print(line)
                last_line = line
            if job["status"] in ("succeeded", "failed", "cancelled", "needs_review"):
                break
            time.sleep(5)

        if job["status"] == "needs_review":
            print("任务需要人工处理：请到控制台“流水线任务中心”查看质量闸门结果并放行")
            return
        if job["status"] != "succeeded":
            raise SystemExit(f"任务未成功：{job['status']} {job.get('error')}")

        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for item in check(client.get(f"/api/v1/pipeline/jobs/{job_id}/artifacts"))["items"]:
            target = out / item["name"]
            with client.stream("GET", item["url"]) as resp:
                resp.raise_for_status()
                with open(target, "wb") as f:
                    for block in resp.iter_bytes(CHUNK):
                        f.write(block)
            ok = sha256_of(target) == item["sha256"]
            print(f"已下载 {target}（{item['size']} 字节，sha256 {'一致' if ok else '不一致！'}）")
        metrics = job.get("metrics") or {}
        print("测试集指标:", json.dumps(metrics.get("evaluate"), ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
