"""
Mosaic 拼图候选服务

工作流：批量随机生成 N 张拼图 -> 落到待定区 -> 人工逐张审核
（采纳 / 丢弃 / 暂留）-> 采纳的写入单独的 xxx_mosaic 数据集。

拼图产物是要进训练集的，所以标签必须跟着一起变换，
由 opencv_service.apply_mosaic_with_labels 保证与像素严格对齐。
"""
import logging
import os
import random
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.crud_dataset import dataset as dataset_crud
from app.models.dataset import Dataset
from app.models.mosaic import MosaicCandidate, MOSAIC_PENDING_LIMIT
from app.services.batch_process_service import batch_process_service
from app.services.opencv_service import opencv_service

logger = logging.getLogger(__name__)

MOSAIC_DIR = Path(settings.STATIC_DIR) / "mosaic_candidates"


class MosaicService:
    """生成、审核、落盘 Mosaic 拼图候选"""

    @staticmethod
    def pending_count(db: Session, source_dataset_id: Optional[str] = None) -> int:
        query = db.query(MosaicCandidate).filter(MosaicCandidate.status == "pending")
        if source_dataset_id:
            query = query.filter(MosaicCandidate.source_dataset_id == source_dataset_id)
        return query.count()

    @classmethod
    def generate(
        cls,
        db: Session,
        source_dataset: Dataset,
        count: int = 20,
        split: str = "train",
        seed: Optional[int] = None,
        output_size: int = 640,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        批量生成拼图候选

        每张拼图随机取 4 张源图（连同它们的标签）拼成一张，
        产物落在待定区等待人工审核，不直接进训练集。

        Args:
            source_dataset: 来源数据集。四张子图必须来自同一个数据集，
                否则 class_id 对不上，会静默产出错标数据
            count: 本次生成几张
            split: 从哪个子集取图
            seed: 随机种子，不传则自动生成并记录，保证可复现
            output_size: 拼图边长
            user_id: 生成者

        Returns:
            生成结果统计
        """
        pending = cls.pending_count(db)
        if pending >= MOSAIC_PENDING_LIMIT:
            raise ValueError(
                f"待审核的拼图已有 {pending} 张，达到上限 {MOSAIC_PENDING_LIMIT} 张。"
                f"请先处理掉一些再生成。"
            )

        room = MOSAIC_PENDING_LIMIT - pending
        requested = max(1, int(count))
        count = min(requested, room)

        pairs = batch_process_service.collect_images(str(source_dataset.path), split)
        labeled_pairs = [(img, lab) for img, lab in pairs if lab]
        if len(labeled_pairs) < 4:
            raise ValueError(
                f"数据集 {source_dataset.name} 的 {split} 子集里带标注的图片不足 4 张，无法拼图"
            )

        if seed is None:
            seed = random.randrange(1, 2 ** 31 - 1)
        rng = random.Random(seed)

        batch_id = str(uuid.uuid4())
        os.makedirs(MOSAIC_DIR, exist_ok=True)
        class_names = list(source_dataset.classes or [])

        created: List[MosaicCandidate] = []
        failed = 0

        for _ in range(count):
            try:
                picked = rng.sample(labeled_pairs, 4)
                images = [opencv_service.read_image(img) for img, _lab in picked]
                labels_list = [opencv_service.load_yolo_labels(lab) for _img, lab in picked]

                mosaic_img, merged_labels = opencv_service.apply_mosaic_with_labels(
                    images, labels_list, output_size=output_size)

                candidate_id = str(uuid.uuid4())
                image_path = MOSAIC_DIR / f"{candidate_id}.jpg"
                opencv_service.save_image(mosaic_img, image_path)

                # 预览图叠加变换后的标注框：人工审核拼图的价值就在于
                # 肉眼确认标签有没有跟着拼对，只看图片是审不出问题的
                preview = opencv_service.draw_yolo_labels(mosaic_img, merged_labels, class_names)
                preview_path = MOSAIC_DIR / f"{candidate_id}_preview.jpg"
                opencv_service.save_image(preview, preview_path)

                candidate = MosaicCandidate(
                    id=uuid.UUID(candidate_id),
                    source_dataset_id=source_dataset.id,
                    source_images=[os.path.relpath(img, str(source_dataset.path))
                                   for img, _lab in picked],
                    image_path=str(image_path),
                    preview_path=str(preview_path),
                    labels=merged_labels,
                    status="pending",
                    seed=seed,
                    batch_id=batch_id,
                    created_by=user_id,
                )
                db.add(candidate)
                created.append(candidate)
            except Exception as exc:
                failed += 1
                logger.error("生成拼图候选失败: %s", exc)

        db.commit()
        for candidate in created:
            db.refresh(candidate)

        result = {
            "batch_id": batch_id,
            "generated": len(created),
            "failed": failed,
            "seed": seed,
            "pending_total": cls.pending_count(db),
            "pending_limit": MOSAIC_PENDING_LIMIT,
        }
        if count < requested:
            # 静默截断会让人以为全生成了，必须说清楚
            result["truncated"] = True
            result["message"] = (
                f"待审核上限为 {MOSAIC_PENDING_LIMIT} 张，本次只生成了 {count} 张"
                f"（申请 {requested} 张）"
            )
        return result

    # ==================== 审核 ====================

    @staticmethod
    def _ensure_target_dataset(db: Session, source: Dataset) -> Dataset:
        """
        懒创建 xxx_mosaic 数据集

        拼图单独存放，不写回源数据集：源数据集会越滚越大且难以回退，
        训练时想不想合并也应该由你自己决定。
        只在第一次采纳时创建，全部丢弃的话不会留下空数据集。
        """
        target_name = f"{source.name}_mosaic"
        existing = dataset_crud.get_by_name(db, name=target_name)
        if existing:
            return existing

        dataset_dir = settings.STATIC_DIR / "datasets" / str(uuid.uuid4())
        os.makedirs(dataset_dir / "train" / "images", exist_ok=True)
        os.makedirs(dataset_dir / "train" / "labels", exist_ok=True)

        classes = list(source.classes or [])
        with open(dataset_dir / "classes.txt", "w", encoding="utf-8") as f:
            for cls in classes:
                f.write(f"{cls}\n")

        with open(dataset_dir / "dataset.yaml", "w", encoding="utf-8") as f:
            f.write(
                f"path: {str(dataset_dir)}\n"
                f"train: train/images\n"
                f"val: train/images\n"
                f"test: train/images\n\n"
                f"# 任务类型: detection, segment, classify, pose, obb\n"
                f"task: {source.task or 'detect'}\n\n"
                f"nc: {len(classes)}\n"
                f"names: {classes}\n"
            )

        return dataset_crud.create_with_fields(db, obj_in={
            "name": target_name,
            "description": f"由 {source.name} 随机 Mosaic 拼图生成，人工审核后采纳",
            "classes": classes,
            "path": str(dataset_dir),
            "image_count": 0,
            "train_count": 0,
            "status": "available",
            "task": source.task or "detect",
        })

    @classmethod
    def accept(cls, db: Session, candidate: MosaicCandidate) -> Dict[str, Any]:
        """采纳：写入目标数据集的 train/images + train/labels"""
        if candidate.status != "pending":
            raise ValueError(f"该候选已被处理过（当前状态：{candidate.status}）")

        source = db.query(Dataset).filter(Dataset.id == candidate.source_dataset_id).first()
        if not source:
            raise ValueError("来源数据集已不存在，无法确定类别表")

        target = cls._ensure_target_dataset(db, source)
        target_dir = Path(str(target.path))
        images_dir = target_dir / "train" / "images"
        labels_dir = target_dir / "train" / "labels"
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)

        name = f"mosaic_{candidate.id}"
        shutil.copy2(candidate.image_path, images_dir / f"{name}.jpg")
        opencv_service.save_yolo_labels(str(labels_dir / f"{name}.txt"),
                                        list(candidate.labels or []))

        candidate.status = "accepted"
        candidate.target_dataset_id = target.id
        candidate.reviewed_at = datetime.utcnow()

        # 计数按目录实际文件数重算，避免多人同时采纳时把计数加飘
        actual = len([p for p in images_dir.iterdir() if p.is_file()])
        target.image_count = actual
        target.train_count = actual

        db.commit()
        db.refresh(candidate)

        return {
            "status": "accepted",
            "target_dataset_id": str(target.id),
            "target_dataset_name": target.name,
            "target_image_count": actual,
        }

    @staticmethod
    def discard(db: Session, candidate: MosaicCandidate) -> Dict[str, Any]:
        """丢弃：删掉待定区的文件并标记状态"""
        if candidate.status != "pending":
            raise ValueError(f"该候选已被处理过（当前状态：{candidate.status}）")

        for path in (candidate.image_path, candidate.preview_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as exc:
                    logger.warning("删除拼图文件失败 %s: %s", path, exc)

        candidate.status = "discarded"
        candidate.reviewed_at = datetime.utcnow()
        db.commit()
        return {"status": "discarded"}

    @staticmethod
    def to_dict(candidate: MosaicCandidate) -> Dict[str, Any]:
        """转成前端用的结构，图片走 /static 直出"""
        def static_url(path: Optional[str]) -> Optional[str]:
            if not path:
                return None
            return f"/static/mosaic_candidates/{os.path.basename(path)}"

        return {
            "id": str(candidate.id),
            "source_dataset_id": str(candidate.source_dataset_id) if candidate.source_dataset_id else None,
            "target_dataset_id": str(candidate.target_dataset_id) if candidate.target_dataset_id else None,
            "source_images": candidate.source_images or [],
            "image_url": static_url(candidate.image_path),
            # 预览图带标注框，审核时应该看这张
            "preview_url": static_url(candidate.preview_path),
            "box_count": len(candidate.labels or []),
            "status": candidate.status,
            "seed": candidate.seed,
            "batch_id": candidate.batch_id,
            "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        }


mosaic_service = MosaicService()
