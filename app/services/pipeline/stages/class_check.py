"""⑤ 视频级类别校验：每个视频抽几帧，用全部类别提问，检查识别结果是否与声明的类别一致

"视频类别选错"会让整段视频的标签全错，而逐帧标注时只问声明的类别，发现不了这个问题。
这里提前抽查，一致率低的视频在质量闸门中暂停，由人确认后再继续。
只有一个类别、或使用 mock 提供方（不具备识别能力）时跳过。

一致率 = 识别出了声明类别（之一）的帧 / 识别出了任何东西的帧。什么都没认出来的帧不计入：
那是漏检（由"未检出比例"闸门管），不是类别选错；把它算进分母会让召回率一般的模型频繁误报暂停。
认出物品的帧少于 MIN_DETECTED 时证据不足，一致率记为空（闸门跳过），不据此暂停。
提问时带上全部类别的参考图（参考图阶段在本阶段之前）：只给文字时，外观相近的类别（绣品与书画）经常混淆，造成误报。
"""
from collections import Counter
from typing import Dict, List, Optional

import numpy as np

from app.services.labeling.vlm_client import VLMAuthError, VLMRequest
from app.services.pipeline import errors
from app.services.pipeline.common import load_videos, read_json, update_video
from app.services.pipeline.errors import PipelineError
from app.services.pipeline.spec import effective_annotate_provider
from app.services.pipeline.stages import references as reference_store
from app.services.pipeline.stages.annotate import make_client

MIN_DETECTED = 3


def run(ctx):
    n = ctx.config.annotate.class_check_frames
    provider, _ = effective_annotate_provider(ctx.config.annotate)
    if len(ctx.classes) < 2 or n == 0 or provider == "mock":
        reason = "只有一个类别" if len(ctx.classes) < 2 else ("已关闭" if n == 0 else "mock 提供方不具备识别能力")
        ctx.update_stage_state(skipped_reason=reason)
        return "skip"

    client = make_client(ctx)
    videos = load_videos(ctx)
    refs = [r for items in reference_store.load(ctx).values() for r in items]
    picks_by_video = {}
    for v in videos:
        if "class_check" in v["stats"]:
            continue
        kept = [f for f in (read_json(ctx.path("manifest", f"{v['key']}.json"), {}) or {}).get("frames", []) if f.get("keep")]
        if kept:
            picks_by_video[v["key"]] = [kept[int(i)] for i in np.linspace(0, len(kept) - 1, min(n, len(kept))).round()]
    # 所有视频的抽查帧一起发：逐个视频发时每批只有几帧，用不满并发
    requests = [VLMRequest(key=f["image"], image_path=ctx.path("images", f["image"]), classes=ctx.classes, references=refs)
                for picks in picks_by_video.values() for f in picks]
    done = [0]

    def on_result(_):
        done[0] += 1
        ctx.progress(done[0] / max(1, len(requests)))

    try:
        results = client.detect_batch(requests, on_result=on_result, should_stop=ctx.is_cancel_requested) if requests else {}
    except VLMAuthError as e:
        raise PipelineError(errors.VLM_UNAVAILABLE, str(e))
    ctx.check_cancel(force=True)
    ctx.add_llm_usage(calls=sum(1 for r in results.values() if not r.cached),
                      cached=sum(1 for r in results.values() if r.cached),
                      failures=sum(1 for r in results.values() if not r.ok),
                      cost=sum(float((r.usage or {}).get("cost") or 0.0) for r in results.values()))
    for v in videos:
        picks = picks_by_video.get(v["key"])
        if not picks:
            continue
        res_list = [results.get(f["image"]) for f in picks]
        check = summarize([{b["label"] for b in res.boxes} if res is not None and res.ok else None for res in res_list],
                          v["class_names"])
        check["frames"] = len(picks)
        update_video(ctx, v["id"], stats={"class_check": check})
        agreement = check["agreement"]
        if agreement is not None and agreement < 0.6:
            declared = "+".join(v["class_names"])
            ctx.warn(f"视频 {v['key']} 可能选错了类别：声明为 {declared}，抽查认出物品的 {check['detected']} 帧中"
                     f"含声明类别的只占 {agreement:.0%}，最多的是 {check['top']}",
                     data={"video": v["key"], "votes": check["votes"]})


def summarize(frame_labels: List[Optional[set]], declared: List[str]) -> Dict:
    """frame_labels：每帧识别出的类别集合（调用失败为 None）"""
    votes = Counter()
    answered = detected = hits = 0
    for labels in frame_labels:
        if labels is None:
            continue
        answered += 1
        if not labels:
            continue
        detected += 1
        hits += bool(labels & set(declared))
        votes.update(labels)
    agreement = round(hits / detected, 4) if detected >= MIN_DETECTED else None
    undeclared = [(c, n) for c, n in votes.most_common() if c not in declared]
    return {"declared": list(declared), "agreement": agreement, "top": votes.most_common(1)[0][0] if votes else None,
            "top_undeclared": undeclared[0][0] if undeclared else None, "votes": dict(votes),
            "answered": answered, "detected": detected, "hits": hits}
