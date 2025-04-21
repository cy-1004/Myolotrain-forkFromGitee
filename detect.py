import argparse
import os
import yaml
import cv2
from pathlib import Path
from ultralytics import YOLO

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='YOLOv8检测脚本')
    parser.add_argument('--weights', type=str, required=True, help='模型权重路径')
    parser.add_argument('--source', type=str, default='0', help='图像源，可以是图像路径、视频路径或摄像头索引')
    parser.add_argument('--img-size', type=int, default=640, help='输入图像大小')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='置信度阈值')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='NMS IoU阈值')
    parser.add_argument('--device', default='', help='cuda设备，例如0或0,1,2,3或cpu')
    parser.add_argument('--save-dir', type=str, default='runs/detect', help='结果保存目录')
    parser.add_argument('--classes', nargs='+', type=int, help='过滤类别')
    parser.add_argument('--view-img', action='store_true', help='显示结果')
    parser.add_argument('--save', action='store_true', default=True, help='保存结果')
    parser.add_argument('--verbose', action='store_true', default=True, help='显示详细信息')
    return parser.parse_args()

def load_config(config_path):
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config

def select_device(device=''):
    """选择设备"""
    if device.lower() == 'cpu':
        return 'cpu'

    if device.lower() == 'cuda':
        return '0'

    # 解析设备索引
    device_ids = [x for x in device.split(',') if x.strip()]
    if device_ids:
        return ','.join(device_ids)

    # 默认使用第一个GPU
    return '0'

def main():
    """主函数"""
    args = parse_args()

    # 设置设备
    device = select_device(args.device)

    # 创建保存目录
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 加载模型
    model = YOLO(args.weights)

    # 运行检测
    results = model.predict(
        source=args.source,
        imgsz=args.img_size,
        conf=args.conf_thres,
        iou=args.iou_thres,
        device=device,
        classes=args.classes,
        save=args.save,
        project=str(save_dir.parent),
        name=save_dir.name,
        exist_ok=True,
        verbose=args.verbose,
        show=args.view_img
    )

    print(f"检测完成！结果保存在 {save_dir}")

if __name__ == '__main__':
    main()
