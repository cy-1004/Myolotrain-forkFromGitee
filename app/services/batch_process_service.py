"""
批量图像处理服务

负责三件事：
1. 从不同来源（上传的一批文件 / 服务器上的数据集 / 标注项目目录）收集待处理图片；
2. 按比例或按张数随机抽样（种子可指定，保证结果可复现、可复查）；
3. 逐张应用预处理操作，并让 YOLO 标签跟着几何变换一起走。

标签处理是这里最容易出错的地方，所以把操作分成三档，见 LABEL_SAFE / LABEL_GEOMETRIC / LABEL_APPROX。
"""
import json
import logging
import os
import random
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.opencv_service import opencv_service

logger = logging.getLogger(__name__)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
YOLO_SPLITS = ('train', 'val', 'test')


class BatchProcessService:
    """批量处理图像，并保持 YOLO 标签与图像同步"""

    # 像素类操作：只改像素值或整体缩放，归一化后的标注框坐标不变，标签原样复制
    LABEL_SAFE = {
        'resize_image',              # YOLO 是归一化坐标，缩放后仍然成立
        'normalize_image',
        'denoise_image',
        'adjust_brightness_contrast',
        'sharpen_image',
        'add_noise',
    }

    # 几何类操作：有精确的标签变换实现，会同步变换标注框
    LABEL_GEOMETRIC = {
        'flip_image',
        'rotate_image',
    }

    # 标签变换只是近似：apply_perspective_transform 的角点偏移是随机的，
    # 而 transform_labels_perspective 只是按强度等比缩小框，并不精确。
    # 对有标注的数据集不建议使用，前端需要显式警告。
    LABEL_APPROX = {
        'apply_perspective_transform',
    }

    ALL_OPS = LABEL_SAFE | LABEL_GEOMETRIC | LABEL_APPROX

    # ==================== 来源收集 ====================

    @classmethod
    def collect_images(cls, root: str, split: str = 'all') -> List[Tuple[str, Optional[str]]]:
        """
        收集目录下的图片，并配对同名标签文件

        兼容两种布局：
        - 标准 YOLO 数据集：{train,val,test}/images/*.jpg + {train,val,test}/labels/*.txt
        - 扁平目录（标注项目的 image_directory）：*.jpg，标签可能不存在

        Args:
            root: 根目录
            split: train / val / test / all，仅对标准 YOLO 布局有意义

        Returns:
            [(图片路径, 标签路径或 None), ...]，按路径排序保证可复现
        """
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"目录不存在: {root}")

        # 判断是不是标准 YOLO 布局
        split_dirs = [d for d in YOLO_SPLITS if (root_path / d / 'images').is_dir()]

        search_roots: List[Path] = []
        if split_dirs:
            wanted = YOLO_SPLITS if split == 'all' else (split,)
            for d in wanted:
                images_dir = root_path / d / 'images'
                if images_dir.is_dir():
                    search_roots.append(images_dir)
            if not search_roots:
                raise ValueError(f"数据集里没有 {split} 子集")
        else:
            search_roots.append(root_path)

        results: List[Tuple[str, Optional[str]]] = []
        for base in search_roots:
            for path in sorted(base.rglob('*')):
                if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                    continue
                label_path = cls.label_path_for(str(path))
                results.append((str(path), label_path if os.path.exists(label_path) else None))

        # 排序后再抽样，保证同一个 seed 每次选中的是同一批图
        results.sort(key=lambda item: item[0])
        return results

    @staticmethod
    def label_path_for(image_path: str) -> str:
        """YOLO 约定：images 目录换成 labels，扩展名换成 .txt"""
        head, _ext = os.path.splitext(image_path)
        parts = Path(head).parts
        # 从右往左找 images 段，避免把路径前面碰巧叫 images 的目录也替换掉
        for i in range(len(parts) - 1, -1, -1):
            if parts[i] == 'images':
                parts = parts[:i] + ('labels',) + parts[i + 1:]
                break
        return str(Path(*parts)) + '.txt'

    # ==================== 随机抽样 ====================

    @staticmethod
    def sample(items: List[Any], mode: str = 'all', value: float = 1.0,
               seed: Optional[int] = None) -> Tuple[List[Any], int]:
        """
        随机抽样

        Args:
            items: 候选列表（调用方需保证已排序）
            mode: all(全部) / ratio(按比例) / count(按张数)
            value: ratio 时是 0~1 的比例，count 时是张数
            seed: 随机种子。不传则随机生成一个并原样返回，
                  调用方必须把它记进 manifest —— 抽样不可复现的话，
                  出了问题没法查是哪一批被改了。

        Returns:
            (抽中的列表, 实际使用的种子)
        """
        if seed is None:
            seed = random.randrange(1, 2 ** 31 - 1)

        if mode == 'all' or not items:
            return list(items), seed

        if mode == 'ratio':
            ratio = max(0.0, min(1.0, float(value)))
            n = int(round(len(items) * ratio))
        elif mode == 'count':
            n = int(value)
        else:
            raise ValueError(f"不支持的抽样方式: {mode}")

        n = max(1, min(len(items), n)) if items else 0

        rng = random.Random(seed)
        selected = rng.sample(items, n)
        # 抽完再排回来，处理顺序稳定，日志和 manifest 也好读
        selected.sort(key=lambda item: item[0] if isinstance(item, tuple) else item)
        return selected, seed

    # ==================== 操作校验 ====================

    @classmethod
    def validate_operations(cls, operations: List[Dict[str, Any]]) -> List[str]:
        """校验操作列表，返回警告信息（不抛异常，让调用方决定怎么呈现）"""
        warnings: List[str] = []
        for op in operations:
            name = op.get('name')
            if name not in cls.ALL_OPS:
                raise ValueError(f"不支持的操作: {name}")
            if name in cls.LABEL_APPROX:
                warnings.append(
                    f"{name} 的标签变换只是近似（透视变换的角点是随机的，"
                    f"标签只按强度等比缩小），有标注的数据集请谨慎使用"
                )
        return warnings

    # ==================== 单张处理 ====================

    @classmethod
    def _apply_operations(cls, img, labels: List[List[float]],
                          operations: List[Dict[str, Any]]):
        """
        对单张图依次应用操作，标签同步变换

        几何操作会改变图像尺寸，所以每步之后都要刷新 (w, h)，
        否则后续的旋转会拿着旧尺寸去算标签。
        """
        height, width = img.shape[:2]

        for op in operations:
            name = op['name']
            params = op.get('params', {}) or {}
            method = getattr(opencv_service, name, None)
            if method is None:
                raise ValueError(f"未知的操作: {name}")

            img = method(img, **params)

            if labels:
                if name == 'flip_image':
                    # cv2.flip 语义：0 = 上下翻转，>0 = 左右翻转，-1 = 两者都做
                    code = int(params.get('flip_code', 1))
                    if code == 0:
                        labels = opencv_service.transform_labels_flip_vertical(labels)
                    elif code > 0:
                        labels = opencv_service.transform_labels_flip_horizontal(labels)
                    else:
                        labels = opencv_service.transform_labels_flip_vertical(
                            opencv_service.transform_labels_flip_horizontal(labels))
                elif name == 'rotate_image':
                    labels = opencv_service.transform_labels_rotate(
                        labels, float(params.get('angle', 0)), width, height)
                elif name == 'apply_perspective_transform':
                    labels = opencv_service.transform_labels_perspective(
                        labels, float(params.get('strength', 0.2)))
                # LABEL_SAFE 的操作不动标签

            height, width = img.shape[:2]

        return img, labels

    # ==================== 批量处理 ====================

    @classmethod
    def run(
        cls,
        pairs: List[Tuple[str, Optional[str]]],
        output_dir: str,
        operations: List[Dict[str, Any]],
        source_root: Optional[str] = None,
        progress_cb: Optional[Callable[[int, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        批量处理

        Args:
            pairs: [(图片路径, 标签路径或 None), ...]
            output_dir: 输出根目录
            operations: 操作列表
            source_root: 源根目录。给了就按相对路径还原目录结构（保持 train/images 布局），
                         不给就全部平铺到 output_dir 下
            progress_cb: (已处理, 失败, 总数) 回调，用于写进度

        Returns:
            统计信息
        """
        os.makedirs(output_dir, exist_ok=True)
        total = len(pairs)
        processed = 0
        failed = 0
        labels_written = 0
        errors: List[Dict[str, str]] = []

        for image_path, label_path in pairs:
            try:
                img = opencv_service.read_image(image_path)
                labels = opencv_service.load_yolo_labels(label_path) if label_path else []

                img, labels = cls._apply_operations(img, labels, operations)

                # 还原相对路径，保住 {split}/images/xxx.jpg 的结构
                if source_root:
                    try:
                        rel = os.path.relpath(image_path, source_root)
                    except ValueError:
                        rel = os.path.basename(image_path)
                else:
                    rel = os.path.basename(image_path)

                out_image = os.path.join(output_dir, rel)
                os.makedirs(os.path.dirname(out_image) or output_dir, exist_ok=True)
                opencv_service.save_image(img, out_image)

                if label_path:
                    out_label = cls.label_path_for(out_image)
                    # 变换后可能一个框都不剩（整个目标被转出画布），
                    # 这时也要写一个空文件，否则 YOLO 会当成"漏标"
                    opencv_service.save_yolo_labels(out_label, labels)
                    labels_written += 1

                processed += 1
            except Exception as exc:
                failed += 1
                errors.append({'image': image_path, 'error': str(exc)})
                logger.error("批量处理失败 %s: %s", image_path, exc)

            if progress_cb:
                progress_cb(processed, failed, total)

        return {
            'total': total,
            'processed': processed,
            'failed': failed,
            'labels_written': labels_written,
            'errors': errors[:50],   # 错误清单只留前 50 条，避免 status.json 爆掉
        }

    # ==================== 任务状态与打包 ====================

    @staticmethod
    def write_status(task_dir: str, **fields: Any) -> None:
        """原子写状态文件：先写临时文件再改名，避免前端轮询到半截 JSON"""
        os.makedirs(task_dir, exist_ok=True)
        path = os.path.join(task_dir, 'status.json')
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(fields, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    @staticmethod
    def read_status(task_dir: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(task_dir, 'status.json')
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            # 极小概率读到正在替换的文件，让前端下次轮询再试
            return None

    @staticmethod
    def write_manifest(task_dir: str, manifest: Dict[str, Any]) -> None:
        """记录这次到底选中了哪些文件、用的什么种子，供事后复查"""
        os.makedirs(task_dir, exist_ok=True)
        with open(os.path.join(task_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    @staticmethod
    def make_zip(source_dir: str, zip_path: str) -> str:
        """把处理结果打包，跳过任务自身的元数据文件"""
        skip = {'status.json', 'status.json.tmp', 'manifest.json', 'result.zip'}
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _dirnames, filenames in os.walk(source_dir):
                for name in filenames:
                    if name in skip:
                        continue
                    full = os.path.join(dirpath, name)
                    zf.write(full, os.path.relpath(full, source_dir))
        return zip_path

    @staticmethod
    def cleanup(path: str) -> None:
        try:
            shutil.rmtree(path)
        except Exception:
            pass


batch_process_service = BatchProcessService()
