from app.services.training_service import get_training_tasks
from app.db.session import SessionLocal

db = SessionLocal()
tasks = get_training_tasks(db)
print('任务ID | 状态')
print('-----|-----')
for task in tasks:
    print(f'{task.id} | {task.status}')
db.close()