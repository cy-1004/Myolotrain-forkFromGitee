"""⑧ 构建数据集：只用可训练的帧，按视频（或时间段）划分 train/val/test，写成 YOLO 格式并登记

为什么不能随机划分：相邻帧几乎一模一样，随机划分会让同一段画面同时出现在训练集和测试集里，
指标虚高，选出来的"最佳模型"不可信。
- by_video：每类视频足够多（剩余视频分完 val 后训练集仍有 ≥ 2 个）时，三个划分都以视频为单位；
- by_video_test：每类 3~4 个视频时，测试集仍整段视频留出（评估指标可信），训练/验证在其余视频内按时间段划分。
  纯按视频分的话 3 个视频只能 1/1/1，训练集只剩三分之一的数据；验证集与训练集同源只影响"选哪个 epoch"，不影响测试指标；
- by_segment：视频不足 min_videos_for_video_split（默认 3）个时，每个视频按时间切成 20 段交错分配，
  段与段交界处 buffer 秒内的帧丢弃（减少相邻帧泄漏）。这种方式测试指标会偏乐观，会在报告和模型卡里注明。
- hybrid：只有部分类别视频不足时，含这些类别的视频按时间段划分，其余视频仍按视频划分——
  不让一个类别的视频少，就把所有类别的测试指标都变成"同源"的。
一个视频可以声明多个类别，按视频划分时一个视频整段只进一个划分，用贪心分配兼顾各类别（见 plan_video_split）。
"""
import random
from typing import Dict, List, Set, Tuple

from app.crud import dataset as dataset_crud
from app.models.annotation import ImageAnnotation
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetCreate
from app.services.labeling import geometry
from app.services.pipeline import errors
from app.services.pipeline.common import link_or_copy, load_videos, write_json
from app.services.pipeline.errors import PipelineError
from app.services.pipeline.stages.gate import frame_is_trainable

SEGMENTS = 20          # 视频足够长时切成的段数（上限）
MIN_SEGMENTS = 5
SPLITS = ("train", "val", "test")


def _segment_pattern(ratios, segments: int = SEGMENTS) -> List[str]:
    """把若干段按比例分给三个划分，并尽量交错（val/test 段均匀散布在视频的不同时间位置）。
    比例为 0 的划分不分配段"""
    n_val = max(1, round(segments * ratios[1])) if ratios[1] > 0 else 0
    n_test = max(1, round(segments * ratios[2])) if ratios[2] > 0 else 0
    pattern = ["train"] * segments
    for k in range(n_test):
        pattern[int((k + 0.5) * segments / n_test)] = "test"
    for k in range(n_val):
        i = int((k + 0.25) * segments / n_val) % segments
        while pattern[i] != "train":
            i = (i + 1) % segments
        pattern[i] = "val"
    return pattern


def segment_plan(span: float, buffer_seconds: float):
    """按视频时长决定段数与实际缓冲带：每段至少约 3 倍缓冲带长，缓冲带不超过段长的 1/4。
    短视频若仍按 20 段切，段长可能比缓冲带还短，验证/测试段的帧会被缓冲带全部吃掉"""
    if buffer_seconds > 0:
        segments = int(min(SEGMENTS, max(MIN_SEGMENTS, round(span / (3 * buffer_seconds)))))
    else:
        segments = SEGMENTS
    seg_len = span / segments
    return segments, min(buffer_seconds, seg_len / 4)


def plan_video_split(video_classes: Dict[str, List[str]], ratios, seed: int) -> Tuple[Dict[str, str], Set[str]]:
    """按视频划分 -> ({视频: train/val/test}, 验证集需要在训练视频里按时间段切的类别)

    每个类别：测试集留出 max(1, round(n×测试比例)) 个视频；留出验证视频后训练视频仍 ≥ 2 个时，
    验证集也按视频（max(1, round(n×验证比例)) 个），否则该类别的验证集在训练视频里按时间段切。
    一个视频可能含多个类别：视频少的类别先挑；挑选时不能让视频里任何类别剩下的视频少于下限；
    同等条件下优先只含少量类别的视频（少占用别的类别的视频）。测试集先按"留 2 个"挑，挑不满再放宽到"留 1 个"。
    """
    keys = sorted(video_classes)
    random.Random(seed).shuffle(keys)
    order = {k: i for i, k in enumerate(keys)}
    classes = sorted({c for cs in video_classes.values() for c in cs})
    total = {c: sum(c in video_classes[k] for k in keys) for c in classes}
    assigned: Dict[str, str] = {}

    def free(c):
        return sum(1 for k in keys if k not in assigned and c in video_classes[k])

    def take(split, quota, keep):
        for c in sorted(classes, key=lambda c: (total[c], c)):
            have = sum(1 for k, sp in assigned.items() if sp == split and c in video_classes[k])
            while have < quota.get(c, 0):
                cands = [k for k in keys if k not in assigned and c in video_classes[k]
                         and all(free(c2) - 1 >= keep for c2 in video_classes[k])]
                if not cands:
                    break
                assigned[min(cands, key=lambda k: (len(video_classes[k]), order[k]))] = split
                have += 1

    test_quota = {c: max(1, round(total[c] * ratios[2])) for c in classes}
    take("test", test_quota, keep=2)
    take("test", test_quota, keep=1)
    val_quota = {}
    for c in classes:
        q = max(1, round(total[c] * ratios[1]))
        val_quota[c] = q if free(c) - q >= 2 else 0
    take("val", val_quota, keep=2)
    for k in keys:
        assigned.setdefault(k, "train")
    segment_val = {c for c in classes if not any(sp == "val" and c in video_classes[k] for k, sp in assigned.items())}
    return assigned, segment_val


def choose_split(video_classes: Dict[str, List[str]], requested: str, min_videos: int) -> Tuple[str, List[str], Set[str]]:
    """决定划分方式 -> (mode, 视频不足的类别, 需要按时间段划分的视频)

    mode：by_video / hybrid / by_segment（by_video 之后还可能因验证集按时间段切而记为 by_video_test）
    """
    videos_by_class: Dict[str, List[str]] = {}
    for k, cs in video_classes.items():
        for c in cs:
            videos_by_class.setdefault(c, []).append(k)
    few = sorted(c for c, keys in videos_by_class.items() if len(keys) < min_videos)
    if requested != "auto":
        mode = requested
    elif not few:
        mode = "by_video"
    else:
        mode = "by_segment" if len(few) == len(videos_by_class) else "hybrid"
    if mode == "by_video" and not all(len(keys) >= 2 for keys in videos_by_class.values()):
        mode = "by_segment"   # 强制按视频但有类别只有 1 个视频
    if mode == "hybrid" and not few:
        mode = "by_video"
    segment_videos = {k for k, cs in video_classes.items() if set(cs) & set(few)} if mode == "hybrid" else set()
    if mode == "hybrid" and len(segment_videos) == len(video_classes):
        mode, segment_videos = "by_segment", set()   # 视频不足的类别出现在每一个视频里，没有可以整段留出的视频
    return mode, few, segment_videos


def assign_by_segment(frames: List[Dict], ratios, buffer_seconds: float) -> Dict[str, str]:
    """frames: 同一视频的 [{"id", "ts"}]。返回 {id: split}，落在缓冲带里的帧不返回（丢弃）"""
    if not frames:
        return {}
    t0 = min(f["ts"] for f in frames)
    t1 = max(f["ts"] for f in frames)
    span = max(t1 - t0, 1e-6)
    segments, buffer_seconds = segment_plan(span, buffer_seconds)
    pattern = _segment_pattern(ratios, segments)
    seg_len = span / segments
    result = {}
    for f in frames:
        pos = (f["ts"] - t0) / span * segments
        seg = min(segments - 1, int(pos))
        split = pattern[seg]
        # 与相邻段划分不同、且离交界不足 buffer 秒的帧丢弃
        offset_in_seg = (pos - seg) * seg_len
        near_prev = seg > 0 and pattern[seg - 1] != split and offset_in_seg < buffer_seconds
        near_next = seg < segments - 1 and pattern[seg + 1] != split and seg_len - offset_in_seg < buffer_seconds
        if near_prev or near_next:
            continue
        result[f["id"]] = split
    return result


def run(ctx):
    cfg = ctx.config.dataset
    drop = ctx.config.annotate.drop_risk_above
    review = ctx.get_artifacts().get("review") or {}
    include_unreviewed = review.get("include_unreviewed", "low_risk")
    project_id = ctx.get_artifacts().get("annotation_project_id")
    videos = {v["key"]: v for v in load_videos(ctx)}
    names = ctx.class_names

    with ctx.session() as db:
        rows = db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id).all()
        frames = []
        for r in rows:
            meta = r.pipeline_meta or {}
            v = videos.get(meta.get("video_key"))
            if v is None or not frame_is_trainable(r, drop, include_unreviewed):
                continue
            size = ((r.auto_annotations or {}).get("meta") or {}).get("image_size") or [0, 0]
            anns = list(r.annotations or [])
            # 帧里实际有框的类别（多类视频里不是每帧都有全部类别；人工确认的无目标帧为空集）
            present = {names[int(a["class_id"])] for a in anns if 0 <= int(a.get("class_id", -1)) < len(names)}
            frames.append({"id": str(r.id), "image": r.image_name, "video": v["key"], "classes": present,
                           "ts": meta.get("ts", 0.0), "annotations": anns, "size": size})

    if not frames:
        raise PipelineError(errors.NO_USABLE_FRAMES, "没有可用于训练的帧（全部被剔除或丢弃）")

    # 视频 -> 声明的类别（只算有可训练帧的视频）
    video_classes = {k: list(videos[k]["class_names"]) for k in dict.fromkeys(f["video"] for f in frames)}
    mode, few, segment_videos = choose_split(video_classes, cfg.split, cfg.min_videos_for_video_split)
    if cfg.split == "by_video" and mode == "by_segment":
        ctx.warn("部分类别只有 1 个视频，无法按视频划分，改为按时间段划分")

    assignment: Dict[str, str] = {}
    frames_by_video: Dict[str, List[Dict]] = {}
    for f in frames:
        frames_by_video.setdefault(f["video"], []).append(f)
    if mode in ("by_video", "hybrid"):
        # 测试集整段视频留出；验证集视频够就按视频，不够就在训练视频里按时间段切（不浪费训练数据）
        train_val_ratio = (cfg.ratios[0] / (cfg.ratios[0] + cfg.ratios[1]), cfg.ratios[1] / (cfg.ratios[0] + cfg.ratios[1]), 0.0)
        planned = {k: cs for k, cs in video_classes.items() if k not in segment_videos}
        video_split, segment_val = plan_video_split(planned, cfg.ratios, cfg.seed)
        for k, split in video_split.items():
            if split == "train" and set(video_classes[k]) & segment_val:
                assignment.update(assign_by_segment(frames_by_video[k], train_val_ratio, cfg.segment_buffer_seconds))
            else:
                assignment.update({f["id"]: split for f in frames_by_video[k]})
        for k in segment_videos:
            assignment.update(assign_by_segment(frames_by_video[k], cfg.ratios, cfg.segment_buffer_seconds))
        if mode == "by_video" and segment_val:
            mode = "by_video_test"
    else:
        for items in frames_by_video.values():
            assignment.update(assign_by_segment(items, cfg.ratios, cfg.segment_buffer_seconds))

    # 兜底：验证集整体为空时训练无法启动（Ultralytics 要求 val 有图）。从每个类别训练帧的时间末尾切出约 15% 作为验证集
    if not any(v == "val" for v in assignment.values()):
        moved = 0
        for cls in videos_by_class:
            train_frames = sorted((f for f in frames if cls in f["classes"] and assignment.get(f["id"]) == "train"),
                                  key=lambda f: (f["video"], f["ts"]))
            n = max(1, round(len(train_frames) * 0.15)) if len(train_frames) >= 2 else 0
            for f in train_frames[-n:] if n else []:
                assignment[f["id"]] = "val"
                moved += 1
        if moved:
            ctx.warn(f"划分后验证集为空，已从训练集末尾挪出 {moved} 帧作为验证集（与训练集同源）")

    # 每个划分都要有每个类别（test 缺类时评估没有意义，train 缺类则学不会）
    coverage = {s: {c: 0 for c in names} for s in SPLITS}
    for f in frames:
        split = assignment.get(f["id"])
        if split:
            for c in f["classes"]:
                coverage[split][c] += 1
    missing_train = [c for c, n in coverage["train"].items() if n == 0]
    if missing_train:
        raise PipelineError(errors.DATASET_FAILED, f"类别 {missing_train} 在训练集中没有样本，无法训练", details=coverage)
    for split in ("val", "test"):
        missing = [c for c, n in coverage[split].items() if n == 0]
        if missing:
            ctx.warn(f"类别 {missing} 在 {split} 集中没有样本，该类别的评估指标不可用", data={"coverage": coverage})

    # 写 YOLO 数据集（图片用硬链接，不额外占空间）
    root = ctx.path("dataset")
    counts = {s: 0 for s in SPLITS}
    split_of_image = {}
    for f in frames:
        split = assignment.get(f["id"])
        if not split:
            continue
        link_or_copy(ctx.path("images", f["image"]), root / split / "images" / f["image"])
        lines = []
        for ann in f["annotations"]:
            if all(k in ann for k in ("x_center", "y_center", "width", "height")):
                lines.append(f"{int(ann['class_id'])} {ann['x_center']:.6f} {ann['y_center']:.6f} "
                             f"{ann['width']:.6f} {ann['height']:.6f}")
        label = root / split / "labels" / (f["image"].rsplit(".", 1)[0] + ".txt")
        label.parent.mkdir(parents=True, exist_ok=True)
        label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        counts[split] += 1
        split_of_image[f["id"]] = split
    for split in SPLITS:
        (root / split / "images").mkdir(parents=True, exist_ok=True)
        (root / split / "labels").mkdir(parents=True, exist_ok=True)

    yaml_text = "\n".join([
        f"path: {root.as_posix()}",
        "train: train/images",
        "val: val/images",
        "test: test/images",
        f"nc: {len(names)}",
        "names:",
        *[f"  {i}: {n}" for i, n in enumerate(names)],
    ]) + "\n"
    (root / "dataset.yaml").write_text(yaml_text, encoding="utf-8")
    (root / "classes.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    write_json(root / "split.json", {"mode": mode, "counts": counts, "coverage": coverage, "assignment": split_of_image})

    # 把划分写回标注记录，控制台可按 train/val/test 筛选查看
    with ctx.session() as db:
        for r in db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id).all():
            meta = dict(r.pipeline_meta or {})
            new_split = split_of_image.get(str(r.id))
            if meta.get("split") != new_split:
                meta["split"] = new_split
                r.pipeline_meta = meta

        artifacts = ctx.get_artifacts()
        ds = db.query(Dataset).filter(Dataset.id == artifacts["dataset_id"]).first() if artifacts.get("dataset_id") else None
        if ds is None:
            ds = dataset_crud.create(db, obj_in=DatasetCreate(
                name=f"[流水线] {ctx.name}", description=f"流水线任务 {ctx.run_id} 构建（{mode}）",
                path=str(root), classes=names, image_count=sum(counts.values()), task="detect"))
        ds.image_count = sum(counts.values())
        ds.train_count, ds.val_count, ds.test_count = counts["train"], counts["val"], counts["test"]
        ds.status = "available"
        ds.classes = names
        dataset_id = str(ds.id)
    ctx.set_artifacts(dataset_id=dataset_id, dataset_dir=str(root))
    segment_classes = few if mode == "hybrid" else (list(names) if mode == "by_segment" else [])
    ctx.set_metrics(dataset={"split_mode": mode, "counts": counts, "coverage": coverage,
                             "leak_warning": mode in ("by_segment", "hybrid"), "segment_classes": segment_classes})
    if mode == "hybrid":
        ctx.warn(f"类别 {few} 的视频少于 {cfg.min_videos_for_video_split} 个，含这些类别的视频按时间段划分，"
                 "这些类别的测试指标会偏乐观；其余视频仍按视频留出测试集", data={"segment_classes": few})
    elif mode == "by_segment":
        ctx.warn("按时间段划分：测试集与训练集来自同一批视频，评估指标会比真实场景偏乐观。每类提供 ≥3 个视频可改为按视频划分")
    elif mode == "by_video_test":
        ctx.event("dataset.split", "测试集按视频留出；每类视频较少，训练/验证在其余视频内按时间段划分（测试指标仍可信）")
