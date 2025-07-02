# YOLOv8 训练脚本
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

def main():
    try:
        # 设置字体路径，避免下载 Arial Unicode 字体
        font_path = r'{}'

        # 设置硬件资源限制
        device_type = '{}'
        cpu_cores = {}
        gpu_memory = {}
        memory_limit = {}

        # 设置运行设备
        os.environ['CUDA_VISIBLE_DEVICES'] = '0' if device_type == 'gpu' else '-1'

        # 如果使用 CPU，设置线程数
        if device_type == 'cpu':
            # 使用全局导入的torch模块
            import torch as torch_local  # 使用不同的名称避免混淆
            torch_local.set_num_threads(cpu_cores)
            print('\n=== 使用 CPU 训练，线程数: ' + str(cpu_cores) + ' ===')
        else:
            print('\n=== 使用 GPU 训练，显存限制 ' + str(gpu_memory) + 'MB ===')

        # 设置内存限制
        import platform
        if platform.system() in ['Linux', 'Darwin']:
            try:
                import resource
                import psutil
                
                # 获取系统总内存
                total_memory = psutil.virtual_memory().total
                available_memory = psutil.virtual_memory().available
                
                # 获取GPU显存信息（如果有）
                gpu_memory = 0
                if torch.cuda.is_available() and device_type == 'gpu':
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory
                
                # 智能计算内存限制
                if gpu_memory > 16 * 1024 * 1024 * 1024:  # 16GB以上显存
                    # 大显存系统使用更宽松的限制（可用内存的90%）
                    calculated_limit = int(available_memory * 0.9)
                    print(f'\n=== 检测到大显存系统({gpu_memory/1024/1024/1024:.1f}GB)，调整内存限制为可用内存的90% ===')
                else:
                    # 普通系统使用传入的memory_limit值
                    calculated_limit = memory_limit * 1024 * 1024
                
                # 确保不超过系统可用内存
                final_limit = min(calculated_limit, available_memory)
                
                # 设置内存限制
                resource.setrlimit(resource.RLIMIT_AS, (final_limit, final_limit))
                print(f'\n=== 内存限制设置为 {final_limit/1024/1024:.0f}MB (系统总内存: {total_memory/1024/1024:.0f}MB, 可用内存: {available_memory/1024/1024:.0f}MB) ===')
                
            except Exception as e:
                # 回退机制：使用传入的memory_limit值
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (memory_limit * 1024 * 1024, memory_limit * 1024 * 1024))
                    print(f'\n=== 警告: 无法智能设置内存限制({str(e)})，使用默认值 {memory_limit}MB ===')
                except:
                    print(f'\n=== 严重警告: 完全无法设置内存限制: {str(e)} ===')
        else:
            # Windows系统不支持resource模块
            print('\n=== Windows系统不支持内存限制设置，内存限制将被忽略 ===')
            print(f'=== 建议内存使用不超过 {memory_limit}MB ===')

        if os.path.exists(font_path):
            print('\n=== 使用项目内置 Arial Unicode 字体: ' + str(font_path) + ' ===')
            matplotlib.rcParams['font.family'] = 'sans-serif'
            matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS']
            os.environ['ULTRALYTICS_FONT'] = font_path
        else:
            print('\n=== 警告: 项目内置 Arial Unicode 字体不存在' + str(font_path) + ' ===')



        # 设置参数
        model_type = '{}'
        dataset_yaml = r'{}'
        epochs = {}
        batch_size = {}
        img_size = {}
        rect = {}
        output_dir = r'{}'
        model_file = r'{}'

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
        # 使用全局导入的torch模块
        try:
            # 导入PyTorch核心类
            from torch.nn.modules.container import Sequential
            from torch.nn import Module, ModuleList, ModuleDict

            # 导入Ultralytics模型类
            from ultralytics.nn.tasks import DetectionModel, SegmentationModel, ClassificationModel, PoseModel

            # 导入Ultralytics模块类
            from ultralytics.nn.modules import conv
            # 只导入需要的模块，避免未使用的导入
            # from ultralytics.nn.modules import block
            # from ultralytics.nn.modules import head

            # 添加PyTorch核心类到安全全局变量
            # 使用全局torch模块
            import torch as torch_global
            torch_global.serialization.add_safe_globals([Sequential, Module, ModuleList, ModuleDict])

            # 添加Ultralytics模型类到安全全局变量
            torch_global.serialization.add_safe_globals([DetectionModel, SegmentationModel, ClassificationModel, PoseModel])

            # 添加Ultralytics模块类
            torch_global.serialization.add_safe_globals([conv.Conv])

            # 添加所有Ultralytics模块类
            # 直接添加常用的类
            try:
                # 添加常用的模块类
                from torch.nn.modules.container import Sequential
                from ultralytics.nn.modules.conv import Conv
                torch_global.serialization.add_safe_globals([Sequential, Conv])
                print('\n=== 成功添加常用模块类到安全全局变量 ===')
            except Exception as e:
                print('\n=== 警告: 无法添加常用模块类到安全全局变量: ' + str(e) + ' ===')

            # 在PyTorch 2.6+中，可以使用weights_only=False参数代替添加安全全局变量
            print('\n=== 使用weights_only=False参数加载模型，避免安全全局变量问题 ===')
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



        # 准备训练参数
        train_args = {{
            'data': dataset_yaml,
            'epochs': epochs,
            'batch': batch_size,
            'imgsz': img_size,
            'project': output_dir,
            'name': 'exp',
            'exist_ok': True,
            'workers': 0,  # 禁用多进程数据加载，避免多进程问题
            'amp': False  # 禁用自动混合精度，避免下载额外模型
        }}

        # 设置环境变量，确保TensorBoard日志写入到正确的位置
        os.environ['ULTRALYTICS_TENSORBOARD'] = '1'

        # 设置Ultralytics的数据集目录为当前项目目录
        import json
        from pathlib import Path
        settings_path = Path.home() / '.config' / 'Ultralytics' / 'settings.json'
        os.makedirs(settings_path.parent, exist_ok=True)
        settings_data = {{'datasets_dir': str(Path.cwd().resolve())}}
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings_data, f)
            print('\n=== 已设置Ultralytics数据集目录为: ' + str(Path.cwd().resolve()) + ' ===\n')
        except Exception as e:
            print('\n=== 警告: 无法设置Ultralytics数据集目录: ' + str(e) + ' ===\n')

        # 如果启用矩形训练，添加rect参数
        if rect:
            train_args['rect'] = True
            print('\n=== 已启用矩形训练模型===')

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