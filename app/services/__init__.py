# Import services
from app.services.dataset_service import create_dataset, get_dataset, get_datasets, delete_dataset
from app.services.model_service import create_model, get_model, get_models, delete_model
from app.services.training_service import create_training_task, start_training, get_training_task, get_training_tasks, stop_training, delete_training_task, get_training_logs, get_training_results
# 重新导入检测服务函数
from app.services.detection_service import create_detection_task, get_detection_task, get_detection_tasks, get_detection_result
