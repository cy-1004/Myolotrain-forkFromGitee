import os
import sys
from datetime import datetime

# 生成测试TensorBoard日志
def create_test_tensorboard_log(log_dir):
    """创建测试TensorBoard日志文件"""
    # 创建events文件（简单的测试内容）
    events_file = os.path.join(log_dir, f'events.out.tfevents.{int(datetime.now().timestamp())}.localhost')
    with open(events_file, 'wb') as f:
        # 写入一些二进制数据作为测试
        f.write(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    print(f'已创建测试TensorBoard日志文件: {events_file}')
    
    # 创建metrics目录
    metrics_dir = os.path.join(log_dir, 'metrics')
    os.makedirs(metrics_dir, exist_ok=True)
    
    # 创建loss.txt文件
    loss_file = os.path.join(metrics_dir, 'loss.txt')
    with open(loss_file, 'w', encoding='utf-8') as f:
        f.write('epoch,loss\n')
        for i in range(5):
            f.write(f'{i},0.5-{i*0.1}\n')
    print(f'已创建测试loss文件: {loss_file}')

# 主函数
if __name__ == '__main__':
    print('=== 生成测试TensorBoard日志 ===')
    
    # 使用原始字符串语法来避免转义问题
    log_dir = r'D:\项目开发\Myolotrain\app\static\models\training_6a1741ee-b8e0-402b-9342-0f84a10b6076\exp'
    print(f'日志目录: {log_dir}')
    
    # 确保目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建测试日志
    create_test_tensorboard_log(log_dir)
    
    # 列出目录内容
    print('\n=== 目录内容 ===')
    for item in os.listdir(log_dir):
        item_path = os.path.join(log_dir, item)
        if os.path.isfile(item_path):
            print(f'文件: {item} ({os.path.getsize(item_path)} 字节)')
        elif os.path.isdir(item_path):
            print(f'目录: {item}')
            # 列出子目录内容
            for sub_item in os.listdir(item_path):
                sub_item_path = os.path.join(item_path, sub_item)
                print(f'  - {sub_item} ({os.path.getsize(sub_item_path)} 字节)')
    
    print('\n=== 测试日志生成完成 ===')
    print('现在TensorBoard应该能够识别到日志文件了。')