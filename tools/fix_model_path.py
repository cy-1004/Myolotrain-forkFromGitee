import os
import shutil
import sys

source_path = r'd:\项目开发\Myolotrain\yolo11n.pt'
dest_dir = r'd:\项目开发\Myolotrain\models'
dest_path = os.path.join(dest_dir, 'yolov8n.pt')

print(f'源文件路径: {source_path}')
print(f'源文件存在: {os.path.exists(source_path)}')
print(f'目标目录: {dest_dir}')
print(f'目标目录存在: {os.path.exists(dest_dir)}')

if not os.path.exists(dest_dir):
    try:
        os.makedirs(dest_dir)
        print(f'已创建目标目录: {dest_dir}')
    except Exception as e:
        print(f'创建目录失败: {e}')
        sys.exit(1)

try:
    shutil.copy2(source_path, dest_path)
    print(f'已成功复制模型文件到: {dest_path}')
    print(f'复制后文件存在: {os.path.exists(dest_path)}')
    if os.path.exists(dest_path):
        print(f'文件大小: {os.path.getsize(dest_path) / 1024 / 1024:.2f} MB')
    # 列出目标目录内容
    print('目标目录内容:')
    for item in os.listdir(dest_dir):
        print(f'  {item}')
except Exception as e:
    print(f'复制文件失败: {e}')
    sys.exit(1)