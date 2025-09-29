import os
import sys
import shutil

# 确保中文显示正常
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

print("=== 模型文件路径测试工具 ===")
print("当前工作目录:", os.getcwd())
print("Python 版本:", sys.version)

# 定义路径变量
base_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(base_dir, 'models')
model_file = os.path.join(models_dir, 'yolov8n.pt')

# 测试文件存在性的几种方式
print("=== 测试模型文件路径:", model_file)
print("文件是否存在?", os.path.exists(model_file))
if os.path.exists(model_file):
    print("文件大小: {:.2f} MB".format(os.path.getsize(model_file) / 1024 / 1024))
    print("绝对路径:", os.path.abspath(model_file))
else:
    print("文件不存在！")

# 测试相对路径
simple_model_file = 'yolov8n.pt'
print("=== 测试简单文件名:", simple_model_file)
print("当前目录下是否存在?", os.path.exists(simple_model_file))

# 测试环境中的yolo11n.pt文件
source_model = os.path.join(base_dir, 'yolo11n.pt')
print("=== 测试源文件:", source_model)
print("源文件是否存在?", os.path.exists(source_model))
if os.path.exists(source_model):
    print("源文件大小: {:.2f} MB".format(os.path.getsize(source_model) / 1024 / 1024))

# 创建正确的模型目录并复制文件
print("=== 创建正确的模型目录并复制文件 ===")
try:
    # 确保models目录存在
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        print("已创建目录:", models_dir)
    else:
        print("目录已存在:", models_dir)
        
    # 复制文件
    if os.path.exists(source_model):
        shutil.copy2(source_model, model_file)
        print("已成功复制", source_model, "到", model_file)
        print("复制后文件是否存在?", os.path.exists(model_file))
        if os.path.exists(model_file):
            print("复制后文件大小: {:.2f} MB".format(os.path.getsize(model_file) / 1024 / 1024))
    else:
        print("源文件不存在:", source_model)
        
    # 同时也复制到当前目录作为yolov8n（解决第二个路径问题）
    current_dir_model = os.path.join(base_dir, 'yolov8n')
    if os.path.exists(source_model):
        shutil.copy2(source_model, current_dir_model)
        print("已成功复制", source_model, "到", current_dir_model)
        print("复制后文件是否存在?", os.path.exists(current_dir_model))
        if os.path.exists(current_dir_model):
            print("复制后文件大小: {:.2f} MB".format(os.path.getsize(current_dir_model) / 1024 / 1024))
        
        # 也创建yolov8n.pt
        current_dir_model_pt = os.path.join(base_dir, 'yolov8n.pt')
        shutil.copy2(source_model, current_dir_model_pt)
        print("已成功复制", source_model, "到", current_dir_model_pt)
        print("复制后文件是否存在?", os.path.exists(current_dir_model_pt))
        
    # 显示目录内容
    print("=== 当前目录内容 ===")
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isfile(item_path):
            print("文件:", item, "({:.2f} MB)".format(os.path.getsize(item_path) / 1024 / 1024))
    
    print("=== models目录内容 ===")
    if os.path.exists(models_dir):
        for item in os.listdir(models_dir):
            item_path = os.path.join(models_dir, item)
            if os.path.isfile(item_path):
                print("文件:", item, "({:.2f} MB)".format(os.path.getsize(item_path) / 1024 / 1024))
    else:
        print("models目录不存在")
        
except Exception as e:
    print("发生错误:", str(e))
    import traceback
    traceback.print_exc()

print("\n=== 测试完成 ===")