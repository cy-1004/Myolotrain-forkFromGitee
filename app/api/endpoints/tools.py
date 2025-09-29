from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.detection_task import DetectionTask

router = APIRouter()


class ReleaseModelRequest(BaseModel):
    model_id: str

@router.post("/release-model")
def release_model(
    request: ReleaseModelRequest,  # 使用请求体接收model_id
    db: Session = Depends(get_db)
):
    model_id = request.model_id
    """
    释放模型与检测任务的关联关系，使模型可以被删除
    由于model_id字段有NOT NULL约束，我们将删除相关的检测任务
    """
    try:
        # 查询使用该模型的所有检测任务
        detection_tasks = db.query(DetectionTask).filter(DetectionTask.model_id == model_id).all()
        
        if not detection_tasks:
            return {
                "success": True,
                "message": "该模型未被任何检测任务使用",
                "released_tasks": 0
            }
        
        # 由于model_id有NOT NULL约束，我们删除相关的检测任务
        released_count = 0
        for task in detection_tasks:
            db.delete(task)
            released_count += 1
        
        # 提交更改到数据库
        db.commit()
        
        return {
            "success": True,
            "message": f"成功删除了{released_count}个使用该模型的检测任务",
            "released_tasks": released_count
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"释放模型失败: {str(e)}"
        )