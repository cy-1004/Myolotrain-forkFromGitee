# YOLOv8 训练与检测平台数据库结构说明

## 1. 数据库概述

YOLOv8 训练与检测平台使用 PostgreSQL 关系型数据库来存储和管理数据。数据库名称为 `yolov8_platform`，包含多个表用于存储数据集、模型、训练任务和检测任务的信息。

数据库使用 SQLAlchemy ORM（对象关系映射）进行访问，这使得应用程序可以通过 Python 对象与数据库进行交互，而不需要直接编写 SQL 查询。

## 2. 数据库表结构

### 2.1 datasets（数据集表）

存储上传的数据集信息。

| 列名 | 数据类型 | 约束 | 描述 |
|------|----------|------|------|
| id | UUID | 主键 | 数据集唯一标识符 |
| name | VARCHAR | 非空，索引 | 数据集名称 |
| description | TEXT | 可空 | 数据集描述 |
| path | VARCHAR | 非空 | 数据集存储路径 |
| classes | JSON | 非空 | 类别列表，JSON 格式 |
| image_count | INTEGER | 默认值 0 | 图像数量 |
| created_at | TIMESTAMP | 默认值 当前时间 | 创建时间 |
| updated_at | TIMESTAMP | 默认值 当前时间，自动更新 | 更新时间 |
| status | VARCHAR | 默认值 "processing" | 数据集状态（processing, available, error） |

### 2.2 models（模型表）

存储上传和训练生成的模型信息。

| 列名 | 数据类型 | 约束 | 描述 |
|------|----------|------|------|
| id | UUID | 主键 | 模型唯一标识符 |
| name | VARCHAR | 非空，索引 | 模型名称 |
| description | TEXT | 可空 | 模型描述 |
| path | VARCHAR | 非空 | 模型存储路径 |
| type | VARCHAR | 非空 | 模型类型（yolov8n, yolov8s, yolov8m, yolov8l, yolov8x） |
| task | VARCHAR | 非空，默认值 "detect" | 任务类型（detect, segment, classify, pose） |
| created_at | TIMESTAMP | 默认值 当前时间 | 创建时间 |
| updated_at | TIMESTAMP | 默认值 当前时间，自动更新 | 更新时间 |
| source | VARCHAR | 默认值 "upload" | 模型来源（upload, training） |

### 2.3 training_tasks（训练任务表）

存储训练任务信息。

| 列名 | 数据类型 | 约束 | 描述 |
|------|----------|------|------|
| id | UUID | 主键 | 训练任务唯一标识符 |
| name | VARCHAR | 非空，索引 | 任务名称 |
| dataset_id | UUID | 外键（datasets.id），非空 | 数据集 ID |
| model_id | UUID | 外键（models.id），可空 | 预训练模型 ID |
| output_model_id | UUID | 外键（models.id），可空 | 输出模型 ID |
| parameters | JSON | 非空 | 训练参数，JSON 格式 |
| hardware_config | JSON | 可空 | 硬件配置，JSON 格式 |
| status | VARCHAR | 默认值 "pending" | 任务状态（pending, downloading_model, training, completed, failed, cancelled） |
| start_time | TIMESTAMP | 可空 | 开始时间 |
| end_time | TIMESTAMP | 可空 | 结束时间 |
| log_path | VARCHAR | 可空 | 日志路径 |
| tensorboard_path | VARCHAR | 可空 | TensorBoard 日志路径 |
| process_id | VARCHAR | 可空 | 训练进程 ID |
| last_checkpoint | VARCHAR | 可空 | 最后一次检查点路径 |

### 2.4 detection_tasks（检测任务表）

存储检测任务信息。

| 列名 | 数据类型 | 约束 | 描述 |
|------|----------|------|------|
| id | UUID | 主键 | 检测任务唯一标识符 |
| model_id | UUID | 外键（models.id），非空 | 模型 ID |
| input_path | VARCHAR | 可空 | 输入文件路径 |
| output_path | VARCHAR | 可空 | 输出文件路径 |
| parameters | JSON | 非空 | 检测参数，JSON 格式 |
| status | VARCHAR | 默认值 "pending" | 任务状态（pending, running, completed, failed） |
| created_at | TIMESTAMP | 默认值 当前时间 | 创建时间 |

## 3. 表关系

### 3.1 训练任务与数据集关系

- 一个数据集可以用于多个训练任务
- 一个训练任务只能使用一个数据集
- 关系类型：多对一（N:1）
- 外键：`training_tasks.dataset_id` 引用 `datasets.id`

### 3.2 训练任务与模型关系

- 一个训练任务可以使用一个预训练模型（可选）
- 一个训练任务可以生成一个输出模型
- 一个模型可以用于多个训练任务
- 关系类型：多对一（N:1）
- 外键：
  - `training_tasks.model_id` 引用 `models.id`（预训练模型）
  - `training_tasks.output_model_id` 引用 `models.id`（输出模型）

### 3.3 检测任务与模型关系

- 一个检测任务使用一个模型
- 一个模型可以用于多个检测任务
- 关系类型：多对一（N:1）
- 外键：`detection_tasks.model_id` 引用 `models.id`

## 4. 数据库初始化

数据库初始化过程包括以下步骤：

1. 创建 `yolov8_platform` 数据库（如果不存在）
2. 创建所有表（如果不存在）
3. 添加必要的索引和约束
4. 检查并修复表结构（如添加缺失的列）

初始化脚本位于 `init_db.py` 和 `app/db/init_db.py`。

## 5. 数据库迁移

数据库迁移使用 Alembic 工具进行管理，迁移脚本位于 `migrations` 目录。

迁移过程包括以下步骤：

1. 生成迁移脚本：`alembic revision --autogenerate -m "描述"`
2. 应用迁移：`alembic upgrade head`

迁移脚本会自动检测模型变化并生成相应的 SQL 语句，以便在不丢失数据的情况下更新数据库结构。

## 6. 数据库配置

数据库连接配置位于 `app/core/config.py` 文件中，包括以下参数：

- 数据库主机：`POSTGRES_SERVER`（默认值：localhost）
- 数据库用户：`POSTGRES_USER`（默认值：postgres）
- 数据库密码：`POSTGRES_PASSWORD`（默认值：postgres）
- 数据库名称：`POSTGRES_DB`（默认值：yolov8_platform）

这些参数可以通过环境变量或 `.env` 文件进行配置。

## 7. 数据库访问模式

应用程序使用以下模式访问数据库：

1. 创建数据库会话：`db = SessionLocal()`
2. 执行数据库操作：`db.query(...)`
3. 提交事务：`db.commit()`
4. 关闭会话：`db.close()`

为了确保会话正确关闭，应用程序使用 FastAPI 的依赖注入系统：

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

API 端点可以通过依赖注入获取数据库会话：

```python
@app.get("/items/")
def read_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

## 8. 数据库备份与恢复

### 8.1 备份数据库

使用 PostgreSQL 的 `pg_dump` 工具备份数据库：

```bash
pg_dump -U postgres -W -F c yolov8_platform > backup.dump
```

### 8.2 恢复数据库

使用 PostgreSQL 的 `pg_restore` 工具恢复数据库：

```bash
pg_restore -U postgres -W -d yolov8_platform backup.dump
```

## 9. 数据库性能优化

为了优化数据库性能，应用程序采用以下策略：

1. 使用索引：为经常查询的列创建索引
2. 连接池：使用 SQLAlchemy 的连接池管理数据库连接
3. 延迟加载：使用 SQLAlchemy 的延迟加载功能，只在需要时加载关联对象
4. 批量操作：使用批量插入和更新操作，减少数据库往返次数
