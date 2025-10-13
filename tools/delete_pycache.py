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
    project_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    print(f"正在清理项目目录: {project_dir}")
    remove_pycache(project_dir)
    print("__pycache__文件夹清理完成")
