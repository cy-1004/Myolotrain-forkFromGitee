"""视觉模型（VLM）自动标注校准：在人工标注过的 YOLO 数据集上，量化 VLM 定位 + SAM 收框的准确度

    python tools/calibrate_vlm.py --dataset app/static/datasets/<id> --per-video 3 \\
        --models qwen/qwen3-vl-30b-a3b-instruct,qwen/qwen3-vl-235b-a22b-instruct \\
        --prompt-mode declared --sam sam2.1_b.pt --out calib.json

- 从数据集里按"来源视频"（文件名 <视频>_<帧号>）每个视频抽 N 帧，覆盖不同视频与类别；
- prompt-mode：declared = 只问该视频里出现过的类别（模拟调用方为每个视频声明类别）；
               all      = 问数据集的全部类别；
- 指标：召回率（人工框被 IoU≥0.5 且类别正确地找到的比例）、精确率、匹配框的平均 IoU、
        类别混淆数、SAM 收框前后的 IoU 变化与回退率、解析失败数、费用与耗时。
上线新模型 / 修改提示词前跑一遍，平均 IoU、召回率明显变差的不要上线。
会实际调用视觉模型接口并产生费用（每张图约 $0.0001~0.001）。
"""
import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from app.services.labeling import geometry
from app.services.labeling import references as refs_lib
from app.services.labeling.sam_refiner import SamRefiner
from app.services.labeling.vlm_client import VLMClient, VLMRequest

# 平台既有文物类别的中文描述（类别名 -> 描述），给视觉模型的提示更具体
KNOWN_PROMPTS = {
    "JadeSeal": "玉玺/玉印（印章形状的玉器）",
    "JadeCup": "玉杯（古代玉质饮器）",
    "CalligraphyPaintings": "书画（悬挂的书法或绘画卷轴）",
    "AncientCloth": "古代织物（绣品、布料）",
    "AncientBowl": "古碗（陶瓷或金属的碗）",
    "Bodhisattva": "菩萨像（佛教造像）",
}
IOU_MATCH = 0.5


def load_dataset(root: Path):
    names = [l.strip() for l in (root / "classes.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    items = []
    for img in sorted(root.rglob("images/*")):
        if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        label = img.parent.parent / "labels" / (img.stem + ".txt")
        if not label.exists():
            continue
        gt = []
        for line in label.read_text(encoding="utf-8").splitlines():
            p = line.split()
            if len(p) == 5:
                gt.append((int(p[0]), *map(float, p[1:])))
        items.append({"path": img, "video": img.stem.rsplit("_", 1)[0], "gt": gt})
    return names, items


def match(preds, gts):
    """preds/gts: [(class_name, xyxy)]，类别相同且 IoU 最大的贪心匹配。返回 (匹配对 [(pi, gi, iou)], 类别混淆数)"""
    pairs = sorted(((geometry.iou(p[1], g[1]), pi, gi) for pi, p in enumerate(preds) for gi, g in enumerate(gts)
                    if p[0] == g[0]), reverse=True)
    used_p, used_g, matched = set(), set(), []
    for iou, pi, gi in pairs:
        if iou < IOU_MATCH or pi in used_p or gi in used_g:
            continue
        used_p.add(pi); used_g.add(gi); matched.append((pi, gi, iou))
    confusions = 0
    for pi, p in enumerate(preds):
        if pi in used_p:
            continue
        if any(geometry.iou(p[1], g[1]) >= IOU_MATCH and p[0] != g[0] for gi, g in enumerate(gts) if gi not in used_g):
            confusions += 1
    return matched, confusions


def build_reference_pool(items, names):
    """每个类别按框面积从大到小排列的候选参考框 [(面积, 视频, 图片路径, yolo 框)]"""
    pool = defaultdict(list)
    for it in items:
        for c, cx, cy, bw, bh in it["gt"]:
            pool[names[c]].append((bw * bh, it["video"], it["path"], (cx, cy, bw, bh)))
    for v in pool.values():
        v.sort(key=lambda x: -x[0])
    return pool


def reference_crop(entry, margin=0.15, max_edge=256) -> bytes:
    _, _, path, (cx, cy, bw, bh) = entry
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    x1, y1 = int(max(0, (cx - bw * (0.5 + margin)) * w)), int(max(0, (cy - bh * (0.5 + margin)) * h))
    x2, y2 = int(min(w, (cx + bw * (0.5 + margin)) * w)), int(min(h, (cy + bh * (0.5 + margin)) * h))
    crop = img[y1:y2, x1:x2]
    scale = max_edge / float(max(crop.shape[:2]))
    if scale < 1:
        crop = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()


def summarize(rows, key):
    gt_total = sum(r["n_gt"] for r in rows)
    pred_total = sum(r[key]["n_pred"] for r in rows)
    tp = sum(len(r[key]["matched"]) for r in rows)
    ious = [m[2] for r in rows for m in r[key]["matched"]]
    return {
        "recall": round(tp / gt_total, 4) if gt_total else None,
        "precision": round(tp / pred_total, 4) if pred_total else None,
        "mean_iou": round(float(np.mean(ious)), 4) if ious else None,
        "confusions": sum(r[key]["confusions"] for r in rows),
        "gt": gt_total, "pred": pred_total, "tp": tp,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--per-video", type=int, default=3)
    ap.add_argument("--models", default="qwen/qwen3-vl-30b-a3b-instruct")
    ap.add_argument("--provider", default="openrouter")
    ap.add_argument("--prompt-mode", choices=["declared", "all"], default="declared")
    ap.add_argument("--prompt-style", choices=["recall", "strict"], default="recall")
    ap.add_argument("--upscale", type=int, default=0, help="长边小于该值的图片放大后再发给模型，0 不放大")
    ap.add_argument("--references", nargs="?", const="gt", default="none", choices=["none", "gt", "auto"],
                    help="每个类别附一张参考裁剪图。gt：取自其他视频的人工框（参考图质量的上限）；"
                         "auto：与流水线相同的自动挑选（先不带参考图检测抽样以外的帧，挑框并核对）")
    ap.add_argument("--probes", type=int, default=48, help="auto 参考图：每个类别最多探测的帧数（分轮，够用即停）")
    ap.add_argument("--sam", default="sam2.1_b.pt", help="SAM 权重名，none 表示不收框")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="calibration.json")
    a = ap.parse_args()

    names, items = load_dataset(Path(a.dataset))
    by_video = defaultdict(list)
    for it in items:
        by_video[it["video"]].append(it)
    # 每个视频"声明"的类别：在该视频至少 10% 的帧里出现过的类别（模拟调用方按视频声明）
    declared = {}
    for vid, its in by_video.items():
        cnt = Counter(names[c] for it in its for c in {g[0] for g in it["gt"]})   # 每类出现在多少帧
        declared[vid] = [c for c, n in cnt.items() if n >= 0.1 * len(its)] or [c for c, _ in cnt.most_common(1)]
    rng = random.Random(a.seed)
    sample = []
    for vid in sorted(by_video):
        its = sorted(by_video[vid], key=lambda x: x["path"].name)
        if len(its) <= a.per_video:
            sample += its
        else:
            idx = np.linspace(0, len(its) - 1, a.per_video).round().astype(int)
            sample += [its[i] for i in idx]
    print(f"数据集 {len(items)} 张、{len(by_video)} 个视频；抽样 {len(sample)} 张；提示方式 {a.prompt_mode}，风格 {a.prompt_style}")

    def class_dicts(class_names):
        return [{"name": n, "prompt": KNOWN_PROMPTS.get(n)} for n in class_names]

    sam = None if a.sam == "none" else SamRefiner(a.sam, {"expand_ratio": 0.02, "min_area_ratio": 0.6, "max_area_ratio": 1.15,
                                                          "max_center_shift_ratio": 0.15, "min_box_area": 16})
    report = {"dataset": a.dataset, "prompt_mode": a.prompt_mode, "prompt_style": a.prompt_style, "upscale": a.upscale,
              "references": a.references, "sample": len(sample), "models": {}}
    for model in [m.strip() for m in a.models.split(",") if m.strip()]:
        client = VLMClient(a.provider, model, cache_dir=Path(a.out).with_suffix("") / "cache", prompt_style=a.prompt_style,
                           min_long_edge=a.upscale, max_long_edge=max(1024, a.upscale))
        pool = build_reference_pool(items, names) if a.references == "gt" else {}
        auto_refs, auto_report = {}, None
        if a.references == "auto":
            sampled = {str(it["path"]) for it in sample}
            frames_by_video = defaultdict(list)
            for it in sorted(items, key=lambda x: x["path"].name):
                if str(it["path"]) not in sampled:
                    frames_by_video[it["video"]].append(it)
            single = [v for v, cs in declared.items() if len(cs) == 1]
            probes_by_class = {}
            for cname in names:
                vids = [v for v in sorted(declared) if cname in declared[v]]
                probes_by_class[cname] = [
                    refs_lib.Probe(key=str(f["path"]), image_path=f["path"], video=f["video"],
                                   classes=class_dicts(declared[f["video"]]))
                    for f in refs_lib.pick_probes(frames_by_video, vids, single, a.probes)]
            auto_refs, auto_report = refs_lib.bootstrap(client, probes_by_class, class_dicts(names))
            print(f"自动参考图：{ {c: len(v) for c, v in auto_refs.items()} }，费用 ${auto_report['usage']['cost']:.5f}")
        ref_cache = {}
        reqs = []
        for i, it in enumerate(sample):
            cls_names = declared[it["video"]] if a.prompt_mode == "declared" else names
            refs = []
            for cname in cls_names if a.references != "none" else []:
                if a.references == "auto":
                    refs += [{"label": r["label"], "image": r["image"]} for r in auto_refs.get(cname, [])]
                    continue
                entry = next((e for e in pool.get(cname, []) if e[1] != it["video"]), None)
                if entry is not None:
                    key = (cname, str(entry[2]))
                    if key not in ref_cache:
                        ref_cache[key] = reference_crop(entry)
                    refs.append({"label": cname, "image": ref_cache[key]})
            reqs.append(VLMRequest(key=str(i), image_path=it["path"], classes=class_dicts(cls_names), references=refs))
        t0 = time.time()
        results = client.detect_batch(reqs)
        elapsed = time.time() - t0
        rows, cost, failures, coord_modes = [], 0.0, 0, Counter()
        for i, it in enumerate(sample):
            res = results[str(i)]
            img = cv2.imdecode(np.fromfile(str(it["path"]), np.uint8), cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
            gts = [(names[c], ((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
                   for c, cx, cy, bw, bh in it["gt"]]
            cost += float((res.usage or {}).get("cost") or 0.0)
            if not res.ok:
                failures += 1
            coord_modes[res.coord_mode] += 1
            preds = [(b["label"], tuple(b["xyxy"])) for b in res.boxes] if res.ok else []
            row = {"image": it["path"].name, "video": it["video"], "n_gt": len(gts), "error": res.error}
            m, conf = match(preds, gts)
            row["vlm"] = {"n_pred": len(preds), "matched": m, "confusions": conf}
            if sam is not None and preds:
                outcomes = sam.refine(img, [p[1] for p in preds])
                refined = [(p[0], tuple(o["xyxy"])) for p, o in zip(preds, outcomes)]
                row["sam_fallbacks"] = sum(o["status"] in ("fallback", "error") for o in outcomes)
            else:
                refined = preds
                row["sam_fallbacks"] = 0
            m2, conf2 = match(refined, gts)
            row["final"] = {"n_pred": len(refined), "matched": m2, "confusions": conf2}
            rows.append(row)
        per_class = {}
        for cname in names:
            sub = []
            for r, it in zip(rows, sample):
                gcls = [names[g[0]] for g in it["gt"]]
                if cname in gcls:
                    sub.append(r)
            if sub:
                per_class[cname] = {"vlm": summarize(sub, "vlm"), "final": summarize(sub, "final")}
        report["models"][model] = {
            "vlm": summarize(rows, "vlm"), "vlm_plus_sam": summarize(rows, "final"),
            "sam_fallback_rate": round(sum(r["sam_fallbacks"] for r in rows) / max(1, sum(r["vlm"]["n_pred"] for r in rows)), 4),
            "parse_or_call_failures": failures, "coord_modes": dict(coord_modes),
            "cost_usd": round(cost, 5), "seconds": round(elapsed, 1), "per_class": per_class,
            "auto_references": auto_report,
            "worst_images": sorted(({"image": r["image"], "gt": r["n_gt"], "pred": r["vlm"]["n_pred"],
                                     "tp": len(r["final"]["matched"]), "error": r["error"]} for r in rows),
                                   key=lambda x: (x["tp"] - x["gt"], -x["pred"]))[:8],
            "rows": rows,
        }
        s = report["models"][model]
        print(f"\n== {model}  ({s['seconds']}s, ${s['cost_usd']}, 失败 {failures}, 坐标约定 {dict(coord_modes)})")
        print(f"   VLM       召回 {s['vlm']['recall']}  精确 {s['vlm']['precision']}  平均IoU {s['vlm']['mean_iou']}  类别混淆 {s['vlm']['confusions']}")
        print(f"   VLM+SAM   召回 {s['vlm_plus_sam']['recall']}  精确 {s['vlm_plus_sam']['precision']}  平均IoU {s['vlm_plus_sam']['mean_iou']}  SAM回退率 {s['sam_fallback_rate']}")
        for cname, st in per_class.items():
            print(f"   {cname:22s} 召回 {st['vlm']['recall']} → {st['final']['recall']}  IoU {st['vlm']['mean_iou']} → {st['final']['mean_iou']}")
    Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n明细已写入 {a.out}")


if __name__ == "__main__":
    main()
