import os
import shutil

def remove_pycache(start_path):
    """
    递归删除指定路径下的所有__pycache__文件夹
    :param start_path: 起始目录路径
    """
    for root, dirs, files in os.walk(start_path):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
                print(f"已删除: {pycache_path}")
            except Exception as e:
                print(f"删除失败 {pycache_path}: {e}")

if __name__ == '__main__':
    parent_dir = os.path.abspath(os.path.join(os.getcwd(), '..'))
    print(f"正在清理上级目录: {parent_dir}")
    remove_pycache(parent_dir)
    print("清理完成")
