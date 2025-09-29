import sys
import os
import warnings
import logging
import multiprocessing

# 禁用自动下载
os.environ['ULTRALYTICS_SKIP_DOWNLOAD'] = '1'
# 禁用AMP检查
os.environ['ULTRALYTICS_SKIP_AMP_CHECK'] = '1'

# 设置多进程启动方法，确保与Windows兼容
import torch
# 在导入任何其他模块之前设置多进程启动方法
torch.multiprocessing.set_start_method('spawn', force=True)

# 覆盖torch.load函数，确保使用weights_only=False
import torch as torch_for_patch
original_torch_load = torch_for_patch.load
def patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
        print('\n=== 覆盖torch.load，使用weights_only=False ===')
    return original_torch_load(*args, **kwargs)
torch_for_patch.load = patched_torch_load

# 禁用matplotlib字体警告
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

import matplotlib

# 强制使用CPU
def force_cpu():
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # 强制禁用GPU
    print('\n=== 环境变量已设置: CUDA_VISIBLE_DEVICES=' + os.environ['CUDA_VISIBLE_DEVICES'] + ' ===')
    
    # 验证是否真的使用CPU
    import torch
    if torch.cuda.is_available():
        print('\n警告: 尽管设置了CUDA_VISIBLE_DEVICES=-1，CUDA仍然可用')
        print('CUDA设备数量: ' + str(torch.cuda.device_count()))
    else:
        print('\n确认: 系统将使用CPU进行训练')

def main():
    try:
        # 强制使用CPU
        force_cpu()
        
        # 设置字体路径，避免下载 Arial Unicode 字体
        font_path = r'D:\项目开发\Myolotrain\app\static\fonts\Arial.Unicode.ttf'

        # 设置硬件资源限制
        device_type = 'cpu'
        cpu_cores = 4
        gpu_memory = None
        memory_limit = 8192

        # 如果使用 CPU，设置线程数
        if device_type == 'cpu':
            import torch as torch_local  # 使用不同的名称避免混淆
            torch_local.set_num_threads(cpu_cores)
            print('\n=== 使用 CPU 训练，线程数: ' + str(cpu_cores) + ' ===')
        else:
            print('\n=== 使用 GPU 训练，显存限制 ' + str(gpu_memory) + 'MB ===')

        if os.path.exists(font_path):
            print('\n=== 使用项目内置 Arial Unicode 字体: ' + str(font_path) + ' ===')
            matplotlib.rcParams['font.family'] = 'sans-serif'
            matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS']
            os.environ['ULTRALYTICS_FONT'] = font_path
        else:
            print('\n=== 警告: 项目内置 Arial Unicode 字体不存在: ' + str(font_path) + ' ===')

        # 设置参数
        model_type = 'yolov8n'
        dataset_yaml = r'D:\项目开发\Myolotrain\datasets_import\门窗检测\dataset.yaml'
        epochs = 5  # 用户选择的训练轮数
        batch_size = 16
        img_size = 640
        rect = False
        output_dir = r'D:\项目开发\Myolotrain\app\static\models\training_6a1741ee-b8e0-402b-9342-0f84a10b6076'
        model_file = r'models\yolov8n.pt'

        # 检查模型文件是否存在
        if not os.path.exists(model_file):
            print('\n=== 警告: 指定的模型文件不存在: ' + str(model_file) + ' ===\n请检查模型路径是否正确')

        print('\n\n\n=== 训练配置信息 ===')
        print('模型类型: ' + str(model_type))
        print('数据集路径: ' + str(dataset_yaml))
        print('训练轮数: ' + str(epochs))
        print('批量大小: ' + str(batch_size))
        print('图像大小: ' + str(img_size))
        print('输出目录: ' + str(output_dir))
        print('模型文件: ' + str(model_file))

        # 检查文件和目录是否存在
        if not os.path.exists(dataset_yaml):
            raise FileNotFoundError('数据集配置文件不存在: ' + str(dataset_yaml))

        if not os.path.exists(model_file):
            raise FileNotFoundError('模型文件不存在: ' + str(model_file))

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 添加安全全局变量
        print('\n=== 添加PyTorch安全全局变量 ===')
        try:
            # 导入PyTorch核心类
            from torch.nn.modules.container import Sequential
            from torch.nn import Module, ModuleList, ModuleDict

            # 导入Ultralytics模型类
            from ultralytics.nn.tasks import DetectionModel, SegmentationModel, ClassificationModel, PoseModel

            # 导入Ultralytics模块类
            from ultralytics.nn.modules import conv

            # 添加PyTorch核心类到安全全局变量
            import torch as torch_global
            torch_global.serialization.add_safe_globals([Sequential, Module, ModuleList, ModuleDict])

            # 添加Ultralytics模型类到安全全局变量
            torch_global.serialization.add_safe_globals([DetectionModel, SegmentationModel, ClassificationModel, PoseModel])

            # 添加Ultralytics模块类
            torch_global.serialization.add_safe_globals([conv.Conv])

            print('\n=== 成功添加常用模块类到安全全局变量 ===')
        except ImportError as e:
            print('\n=== 警告: 无法导入所需类: ' + str(e) + ' ===')

        # 导入 YOLO
        print('\n=== 导入 YOLO 模块 ===')
        from ultralytics import YOLO

        # 加载模型
        print('\n=== 加载模型: ' + str(model_file) + ' ===')
        print('\n=== 模型文件是否存在: ' + str(os.path.exists(model_file)) + ' ===')
        print('\n=== 模型文件大小: ' + str(os.path.getsize(model_file) / (1024 * 1024)) + ' MB ===')

        # 使用用户上传的模型文件
        model = YOLO(model_file)

        # 开始训练
        print('\n=== 开始训练数据集配置文件=' + str(dataset_yaml) + ', 轮数=' + str(epochs) + ', 批量=' + str(batch_size) + ', 图像大小=' + str(img_size) + ', 矩形训练=' + str(rect) + ' ===')

        # 准备训练参数 - 设置resume=False以开始新的训练
        train_args = {
            'device': 'cpu',  # 明确指定使用CPU训练
            'data': dataset_yaml,
            'epochs': epochs,
            'batch': batch_size,
            'imgsz': img_size,
            'project': output_dir,
            'name': 'exp',
            'exist_ok': True,
            'workers': 0,  # 禁用多进程数据加载，避免多进程问题
            'amp': False,  # 禁用自动混合精度，避免下载额外模型
            'resume': False  # 重要！设置为False以开始新的训练，而不是尝试恢复已完成的训练
        }

        # 如果启用矩形训练，添加rect参数
        if rect:
            train_args['rect'] = True
            print('\n=== 已启用矩形训练模型===')

        # 设置环境变量，确保TensorBoard日志写入到正确的位置
        os.environ['ULTRALYTICS_TENSORBOARD'] = '1'

        # 设置Ultralytics的数据集目录为当前项目目录
        import json
        from pathlib import Path
        settings_path = Path.home() / '.config' / 'Ultralytics' / 'settings.json'
        os.makedirs(settings_path.parent, exist_ok=True)
        settings_data = {'datasets_dir': str(Path.cwd().resolve())}
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings_data, f)
            print('\n=== 已设置Ultralytics数据集目录为: ' + str(Path.cwd().resolve()) + ' ===\n')
        except Exception as e:
            print('\n=== 警告: 无法设置Ultralytics数据集目录: ' + str(e) + ' ===\n')

        # 开始训练
        results = model.train(**train_args)

        print('\n\n=== 训练完成 ===')
        print('\n结果摘要: ' + str(results))

    except Exception as e:
        import traceback
        print('\n\n=== 训练过程中出现错误===')
        print('\n错误信息: ' + str(e))
        print('\n详细错误堆栈:')
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    # 在Windows上必须添加这一行，解决多进程问题
    multiprocessing.freeze_support()
    main()