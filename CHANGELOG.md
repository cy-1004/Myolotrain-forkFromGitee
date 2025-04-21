# Myolotrain 系统更新日志

## [0.1.0] - 2025-04-21

### 新增
- 创建系统更新日志，记录系统更新进展

### 修改
- 修改`import_local_dataset`函数，支持直接引用`datasets_import`目录中的原始数据集
  - 当用户选择"服务器数据集"时，系统不再移动数据集目录，而是直接引用原始目录
  - 在数据库中标记为外部数据集（`is_external=True`）
  - 在原始目录创建必要的目录结构和配置文件

- 修改`import_external_dataset`函数，与`import_local_dataset`保持一致
  - 直接引用原始目录，不创建别名目录
  - 验证或创建dataset.yaml文件，确保训练过程能正确找到数据集

- 修改`delete_dataset`函数，确保不会删除外部数据集的目录
  - 当删除数据集时，检查是否为外部数据集（`is_external=True`）
  - 如果是外部数据集，只删除数据库记录，不删除目录

- 修复训练脚本模板中的格式化问题
  - 在`train_script_template.py`中使用双花括号转义字典定义，避免与格式化占位符冲突
  - 在`training_service.py`中处理这些双花括号，确保脚本正确生成

- 修复数据集路径问题
  - 在`dataset.yaml`文件中使用绝对路径而不是相对路径
  - 为训练、验证和测试集指定完整的绝对路径，避免路径解析错误

- 修复Ultralytics数据集目录设置
  - 在训练脚本中设置Ultralytics的数据集目录为当前项目目录
  - 避免使用默认的`D:\AI\zljc\yolov5-master\datasets`目录

- 禁用自动混合精度(AMP)检查
  - 在训练脚本中设置`amp=False`参数，避免下载额外模型
  - 设置环境变量`ULTRALYTICS_SKIP_AMP_CHECK=1`，禁用AMP检查
  - 修复恢复训练时的参数设置，确保一致性

### 计划中的更改
- 进一步优化外部数据集的处理，提高训练效率