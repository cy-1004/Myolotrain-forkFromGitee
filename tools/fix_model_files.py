import os
import shutil

print('=== 简单模型文件修复工具 ===')

# 获取当前目录
base_dir = os.getcwd()
print('当前工作目录:', base_dir)

# 定义路径
source_file = os.path.join(base_dir, 'yolo11n.pt')
models_dir = os.path.join(base_dir, 'models')
target_file1 = os.path.join(models_dir, 'yolov8n.pt')
target_file2 = os.path.join(base_dir, 'yolov8n')
target_file3 = os.path.join(base_dir, 'yolov8n.pt')

# 检查源文件是否存在
print('\n检查源文件:', source_file)
if not os.path.exists(source_file):
    print('错误: 源文件yolo11n.pt不存在!')
    exit(1)
else:
    print('源文件存在，大小:', round(os.path.getsize(source_file)/1024/1024, 2), 'MB')

# 创建models目录
print('\n创建models目录:', models_dir)
if not os.path.exists(models_dir):
    os.makedirs(models_dir)
    print('已创建目录')
else:
    print('目录已存在')

# 复制文件到三个不同位置
try:
    # 复制到models目录下的yolov8n.pt
    shutil.copy2(source_file, target_file1)
    print('已复制到:', target_file1)
    print('文件存在:', os.path.exists(target_file1))
    
    # 复制到当前目录下的yolov8n（无扩展名）
    shutil.copy2(source_file, target_file2)
    print('已复制到:', target_file2)
    print('文件存在:', os.path.exists(target_file2))
    
    # 复制到当前目录下的yolov8n.pt
    shutil.copy2(source_file, target_file3)
    print('已复制到:', target_file3)
    print('文件存在:', os.path.exists(target_file3))
    
    # 显示目录内容
    print('\n=== models目录内容 ===')
    for item in os.listdir(models_dir):
        print('文件:', item)
        
    print('\n=== 当前目录中的模型文件 ===')
    for item in os.listdir(base_dir):
        if item.startswith('yolo'):
            print('文件:', item)
            
    print('\n=== 修复完成！===')
    print('现在应该可以解决模型文件路径问题了。')
    
except Exception as e:
    print('复制过程中发生错误:', str(e))
    import traceback
    traceback.print_exc()