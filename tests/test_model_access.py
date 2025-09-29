import os
import sys
import traceback

def check_model_file():
    model_path = r'd:\项目开发\Myolotrain\models\yolov8n.pt'
    
    print(f'当前工作目录: {os.getcwd()}')
    print(f'检查模型文件: {model_path}')
    print(f'文件是否存在: {os.path.exists(model_path)}')
    
    if os.path.exists(model_path):
        print(f'文件大小: {os.path.getsize(model_path) / 1024 / 1024:.2f} MB')
        print(f'文件绝对路径: {os.path.abspath(model_path)}')
        
        # 尝试读取文件头
        try:
            with open(model_path, 'rb') as f:
                header = f.read(10)
                print(f'文件头: {header.hex()}')
        except Exception as e:
            print(f'读取文件失败: {e}')
            
        # 尝试使用ultralytics加载模型
        try:
            print('\n尝试使用ultralytics加载模型...')
            from ultralytics import YOLO
            model = YOLO(model_path)
            print('模型加载成功！')
            print(f'模型信息: {model.info()}')
        except Exception as e:
            print(f'模型加载失败: {e}')
            traceback.print_exc()
    else:
        # 检查目录结构
        parent_dir = os.path.dirname(model_path)
        print(f'\n检查父目录: {parent_dir}')
        print(f'父目录是否存在: {os.path.exists(parent_dir)}')
        if os.path.exists(parent_dir):
            print('父目录内容:')
            try:
                for item in os.listdir(parent_dir):
                    item_path = os.path.join(parent_dir, item)
                    print(f'  {item} - 大小: {os.path.getsize(item_path)/1024/1024:.2f}MB' if os.path.isfile(item_path) else f'  {item} (目录)')
            except Exception as e:
                print(f'列出目录内容失败: {e}')
    
if __name__ == '__main__':
    check_model_file()