"""④ 参考图：每个类别准备一张"它长这样"的裁剪图，随标注请求一起发给视觉模型

实测效果见 app/services/labeling/references.py：放大 + 参考图让召回率从 0.41 升到 0.74，
自动挑选的参考图（0.72）与人工框裁出来的（0.74）几乎一样。

- 调用方提供的参考图（创建任务时已标准化存进 references/provided/）优先；
- 没提供的类别（references=auto 时）从视频里自动挑：只放大、不带参考图检测探测帧 → 挑候选 → 核对；
- 结果存为 references/<类别>_<序号>.jpg + references.json，已有结果时直接复用（可重复执行）。
  控制台展示每个类别用的参考图——参考图挑错了会把整个类别带偏，人一眼就能看出来。

本阶段排在类别校验之前，类别校验也带参考图提问：只凭文字描述时，模型会把绣品认成"书画"之类，
把类别声明正确的视频误报为"选错了类别"。视频类别真选错时，从它身上挑出的候选在核对时会被认成真实类别（contradicted）而丢弃。
"""
from pathlib import Path
from typing import Dict, List

from app.services.labeling import references as refs_lib
from app.services.labeling.vlm_client import VLMAuthError
from app.services.pipeline import errors
from app.services.pipeline.common import load_videos, read_json, write_json
from app.services.pipeline.errors import PipelineError
from app.services.pipeline.spec import effective_annotate_provider

PROVIDED_DIR = ("references", "provided")
INDEX = ("references", "references.json")


def provided_paths(run_root: Path, class_name: str) -> List[Path]:
    return sorted((run_root.joinpath(*PROVIDED_DIR)).glob(f"{class_name}_*.jpg"))


def save_provided(run_root: Path, prepared: Dict[str, List[bytes]]):
    """创建任务时保存调用方提供的参考图（已经过 reference_from_upload 标准化）"""
    folder = run_root.joinpath(*PROVIDED_DIR)
    for name, images in prepared.items():
        for i, data in enumerate(images):
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{name}_{i + 1}.jpg").write_bytes(data)


def load(ctx, per_class: int = None) -> Dict[str, List[Dict]]:
    """本 Run 选定的参考图 {类别: [{"label", "image": JPEG 字节}]}；还没有结果时退回调用方提供的"""
    per_class = per_class or ctx.config.annotate.references_per_class
    if ctx.config.annotate.references == "off":
        return {}
    out: Dict[str, List[Dict]] = {}
    index = read_json(ctx.path(*INDEX))
    if index is not None:
        for name, items in (index.get("classes") or {}).items():
            for it in items[:per_class]:
                p = ctx.path("references", it["file"])
                if p.exists():
                    out.setdefault(name, []).append({"label": name, "image": p.read_bytes()})
        return out
    for name in ctx.class_names:
        for p in provided_paths(ctx.dir, name)[:per_class]:
            out.setdefault(name, []).append({"label": name, "image": p.read_bytes()})
    return out


def run(ctx):
    from app.services.pipeline.stages.annotate import check_budget, make_client

    cfg = ctx.config.annotate
    if ctx.stage_state("annotate").get("status") == "completed":
        ctx.update_stage_state(skipped_reason="标注已完成（本阶段上线前创建的任务）")
        return "skip"
    if cfg.references == "off":
        ctx.update_stage_state(skipped_reason="已关闭（annotate.references=off）")
        return "skip"
    if read_json(ctx.path(*INDEX)) is not None:
        return None   # 已有结果（续跑）

    provider, _ = effective_annotate_provider(cfg)
    chosen: Dict[str, List[Dict]] = {}
    for name in ctx.class_names:
        paths = provided_paths(ctx.dir, name)[:cfg.references_per_class]
        if paths:
            chosen[name] = [{"image": p.read_bytes(), "source": {"type": "provided", "file": p.name}} for p in paths]

    need = [n for n in ctx.class_names if n not in chosen] if cfg.references == "auto" else []
    report = None
    if need and provider == "mock":
        need = []   # mock 不认图，也用不上参考图
    if need:
        client = make_client(ctx)
        videos = load_videos(ctx)
        classes_by_name = {c["name"]: c for c in ctx.classes}

        frames_by_video, video_classes = {}, {}
        for v in videos:
            kept = [f for f in (read_json(ctx.path("manifest", f"{v['key']}.json"), {}) or {}).get("frames", [])
                    if f.get("keep")]
            frames_by_video[v["key"]] = [{"image": f["image"], "video": v["key"]} for f in kept]
            video_classes[v["key"]] = [classes_by_name[n] for n in v["class_names"]]
        single = [k for k, cs in video_classes.items() if len(cs) == 1]
        probes_by_class = {}
        for name in need:
            vids = [v["key"] for v in videos if name in v["class_names"] and v["key"] in frames_by_video]
            probes_by_class[name] = [
                refs_lib.Probe(key=f["image"], image_path=ctx.path("images", f["image"]), video=f["video"],
                               classes=video_classes[f["video"]])
                for f in refs_lib.pick_probes(frames_by_video, vids, single, cfg.reference_probe_frames)]
        # 进度按探测上限估算（够用即停，实际请求数通常更少）
        expected = sum(len(v) for v in probes_by_class.values()) + 3 * len(probes_by_class)
        done = [0]

        def on_result(_):
            done[0] += 1
            ctx.progress(min(0.99, done[0] / max(1, expected)), detail={"requests": done[0]})

        try:
            auto, report = refs_lib.bootstrap(client, probes_by_class, ctx.classes, per_class=cfg.references_per_class,
                                              should_stop=ctx.is_cancel_requested, on_result=on_result)
        except VLMAuthError as e:
            raise PipelineError(errors.VLM_UNAVAILABLE, str(e))
        ctx.check_cancel(force=True)
        u = report["usage"]
        total = ctx.add_llm_usage(calls=u["calls"], cached=u["cached"], failures=u["failures"],
                                  prompt_tokens=u["prompt_tokens"], completion_tokens=u["completion_tokens"], cost=u["cost"])
        for name, items in auto.items():
            chosen[name] = [{"image": it["image"], "source": it["source"]} for it in items]
        check_budget(ctx, total)

    index = {"classes": {}, "missing": [], "report": report}
    for name in ctx.class_names:
        items = []
        for i, it in enumerate(chosen.get(name, [])):
            file = f"{name}_{i + 1}.jpg"
            ctx.path("references").mkdir(parents=True, exist_ok=True)
            ctx.path("references", file).write_bytes(it["image"])
            items.append({"file": file, **it["source"]})
        if items:
            index["classes"][name] = items
        else:
            index["missing"].append(name)
    write_json(ctx.path(*INDEX), index)
    ctx.set_artifacts(references={"classes": index["classes"], "missing": index["missing"]})
    unchecked = [name for name, items in index["classes"].items()
                 if any(i.get("type") == "auto" and i.get("verdict") != "confirmed" for i in items)]
    if unchecked:
        ctx.warn(f"类别 {unchecked} 的参考图未经模型核对（只出现在多类视频里、或物件太小），"
                 "请在控制台“类别”卡片里确认挑的是不是该文物；挑错了建议提供参考图后重新提交",
                 data={"unchecked": unchecked})
    if index["missing"] and provider != "mock":
        ctx.warn(f"类别 {index['missing']} 没有参考图，这些类别的自动标注召回会明显偏低（实测约低一半）。"
                 "建议在创建任务时为它们提供参考图（classes[].references）", data={"missing": index["missing"]})
    ctx.event("references.ready", f"参考图：{len(index['classes'])}/{len(ctx.class_names)} 个类别"
              + ("（含调用方提供）" if any(i.get("type") == "provided" for v in index["classes"].values() for i in v) else ""),
              data={"classes": {k: [i.get("type") for i in v] for k, v in index["classes"].items()}})
    return None
