from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def get_multi_by_status(
        self, db: Session, *, status: Union[str, List[str]], skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        根据状态获取多个对象

        参数:
            db: 数据库会话
            status: 单个状态字符串或状态列表
            skip: 跳过数量
            limit: 限制数量

        返回:
            符合状态条件的对象列表
        """
        # 检查模型是否有status属性
        if not hasattr(self.model, 'status'):
            raise AttributeError(f"Model {self.model.__name__} does not have 'status' attribute")

        query = db.query(self.model)

        # 如果状态是列表，使用in_操作符
        if isinstance(status, list):
            query = query.filter(self.model.status.in_(status))
        else:
            # 否则使用等于操作符
            query = query.filter(self.model.status == status)

        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_with_fields(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create a new record with explicit fields.
        This is useful when the CreateSchemaType doesn't include all required fields.

        :param db: Database session
        :param obj_in: Dictionary with field values
        :return: Created model instance
        """
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> ModelType:
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj
