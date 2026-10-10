import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, BackgroundTasks
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID
from app.core.config import settings
from app.db.session import get_db
from app.crud import annotation_project, image_annotation
from app.crud.crud_model import model
from app.api.deps import get_current_active_user
from app.api.deps import forbid_in_external_mode
from app.models.annotation import ANNOTATION_LEASE_TTL, ImageAnnotation as ImageAnnotationModel
from app.models.user import User, UserRole
from app.schemas.annotation import (
    AnnotationProjectCreate, AnnotationProjectResponse, AnnotationProjectUpdate,
    ImageAnnotationCreate, ImageAnnotation, ImageAnnotationUpdate,
    ProjectStats, ExportRequest, MergeProjectsRequest,
    LeaseHolder, LeaseResponse, NextImageResponse, PresenceEntry, PresenceResponse
)
from app.services.annotation_service import AnnotationService

router = APIRouter()

# ---------------------------------------------------------------------------
# 多人协作：标注租约
#
# 标注是"一人一图"的独占工作，不存在同一张图共同编辑的需求，因此不引入
# WebSocket 实时协同，只保证互斥：
#   1. 打开图片时获取租约（软锁），他人看到只读提示；
#   2. 租约 ANNOTATION_LEASE_TTL 后过期、前端定时续期，浏览器崩溃也不会把图锁死；
#   3. 保存时再校验版本号，兜住"租约刚过期"这类边界情况，冲突返回 409 而非静默覆盖。
# ---------------------------------------------------------------------------

def _lease_available(user_id: int, now: datetime):
    """租约可被 user_id 取得的条件：无人持有 / 自己持有 / 他人租约已过期"""
    return or_(
        ImageAnnotationModel.locked_by.is_(None),
        ImageAnnotationModel.locked_by == user_id,
        ImageAnnotationModel.locked_at < now - ANNOTATION_LEASE_TTL,
    )

def _lease_held_by_other(image: ImageAnnotationModel, user_id: int, now: datetime) -> bool:
    """图片是否正被他人的有效租约占用"""
    if image.locked_by is None or image.locked_by == user_id or image.locked_at is None:
        return False
    return image.locked_at >= now - ANNOTATION_LEASE_TTL

def _username(db: Session, user_id: Optional[int]) -> Optional[str]:
    if user_id is None:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    return user.username if user else None

def _lease_conflict(db: Session, image: ImageAnnotationModel) -> HTTPException:
    """423：图片被他人租约占用，前端据此进入只读模式并显示持有者"""
    return HTTPException(status_code=423, detail={
        "message": "该图片正在被他人标注",
        "holder": {
            "user_id": image.locked_by,
            "username": _username(db, image.locked_by) or "未知用户",
            "locked_at": image.locked_at.isoformat() if image.locked_at else None,
        },
    })

def _acquire_lease(db: Session, image_id: UUID, user: User, force: bool = False) -> ImageAnnotationModel:
    """原子地获取或续期租约

    用单条带条件的 UPDATE 做 compare-and-swap，由数据库行锁保证互斥；
    若先 SELECT 再 UPDATE，两个并发请求会双双通过检查。
    """
    now = datetime.utcnow()
    conditions = [ImageAnnotationModel.id == image_id]
    if not force:
        conditions.append(_lease_available(user.id, now))

    result = db.execute(
        update(ImageAnnotationModel)
        .where(*conditions)
        .values(
            locked_by=user.id,
            locked_at=now,
            # 自赋值以压制 updated_at 的 onupdate，否则每次心跳续期都会
            # 把图片显示成"刚刚修改过"
            updated_at=ImageAnnotationModel.updated_at,
        )
    )
    db.commit()

    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    if result.rowcount == 0:
        raise _lease_conflict(db, image)
    return image

@router.get("/test")
def test_annotation():
    """测试标注API"""
    return {"message": "Annotation API is working"}

@router.post("/projects/", response_model=AnnotationProjectResponse)
def create_annotation_project(
    project: AnnotationProjectCreate,
    db: Session = Depends(get_db)
):
    """创建标注项目"""
    service = AnnotationService()
    
    # 提取import_original_annotations并从project中排除
    import_original_annotations = getattr(project, 'import_original_annotations', False)
    
    # 创建项目数据字典，排除import_original_annotations
    project_data_dict = project.model_dump()
    project_data_dict.pop('import_original_annotations', None)
    
    # 创建项目
    project_data = AnnotationProjectCreate(**project_data_dict)
    proj = service.create_project(db=db, project_data=project_data)
    
    # 如果需要导入原标注，则执行导入
    if import_original_annotations:
        import_result = service._import_existing_annotations_with_stats(db, proj)
        # 构建完整的响应数据，确保所有字段都正确序列化
        result = {
            'id': proj.id,
            'name': proj.name,
            'description': proj.description,
            'dataset_id': proj.dataset_id,
            'classes': proj.classes,
            'class_keypoints': proj.class_keypoints,
            'image_directory': proj.image_directory,
            'project_type': proj.project_type,
            'import_original_annotations': proj.import_original_annotations,
            'created_at': proj.created_at,
            'updated_at': proj.updated_at,
            'status': proj.status,
        }
        result['import_result'] = import_result
        return result
    else:
        return proj

@router.post("/projects/from-directory", response_model=AnnotationProjectResponse, dependencies=[Depends(forbid_in_external_mode)])
def create_project_from_directory(
    name: str = Body(...),
    description: str = Body(""),
    project_type: str = Body("detection"),
    classes: List[str] = Body(...),
    image_directory: str = Body(...),
    import_original_annotations: bool = Body(False),
    db: Session = Depends(get_db)
):
    """从目录创建标注项目"""
    # 创建项目数据对象，不包含import_original_annotations
    project_data = AnnotationProjectCreate(
        name=name,
        description=description,
        project_type=project_type,
        classes=classes,
        image_directory=image_directory
    )
    
    service = AnnotationService()
    # 调用服务方法，传入额外的导入标志
    project = service.create_project(db=db, project_data=project_data)
    
    # 如果需要导入原标注，则执行导入
    if import_original_annotations:
        import_result = service._import_existing_annotations_with_stats(db, project)
        # 构建完整的响应数据，确保所有字段都正确序列化
        result = {
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'dataset_id': project.dataset_id,
            'classes': project.classes,
            'class_keypoints': project.class_keypoints,
            'image_directory': project.image_directory,
            'project_type': project.project_type,
            'import_original_annotations': project.import_original_annotations,
            'created_at': project.created_at,
            'updated_at': project.updated_at,
            'status': project.status,
        }
        result['import_result'] = import_result
        return result
    else:
        return project

@router.get("/projects/")
def get_annotation_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取标注项目列表"""
    return annotation_project.get_multi(db, skip=skip, limit=limit)

@router.get("/projects/{project_id}", response_model=AnnotationProjectResponse)
def get_annotation_project(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """获取单个标注项目"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    return project

@router.put("/projects/{project_id}", response_model=AnnotationProjectResponse)
def update_annotation_project(
    project_id: UUID,
    project_update: AnnotationProjectUpdate,
    db: Session = Depends(get_db)
):
    """更新标注项目"""
    project = annotation_project.get(db, id=project_id)
    if project and project.review_required and project_update.classes is not None \
            and list(project_update.classes) != list(project.classes or []):
        # 流水线项目的类别顺序即 class_id，一路带到 labels.txt；改动会让已有标注和端侧的类别对不上
        raise HTTPException(status_code=403, detail="流水线项目的类别列表已冻结，不能修改")
    service = AnnotationService()
    return service.update_annotation_project(db, project_id, project_update)

@router.delete("/projects/{project_id}")
def delete_annotation_project(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """删除标注项目"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    # 获取项目目录并删除实际文件
    import shutil
    import os
    from pathlib import Path
    
    if project.image_directory:
        project_dir = Path(project.image_directory)
        # 如果image_directory指向的是项目的images子目录，则获取父目录
        if project_dir.name == "images":
            project_dir = project_dir.parent
        if project_dir.exists() and str(project_dir).startswith(str(settings.STATIC_DIR / "annotations")):
            # 确保只删除annotations目录下的项目目录，防止误删其他目录
            try:
                shutil.rmtree(project_dir)
                logging.info(f"成功删除项目目录: {project_dir}")
            except Exception as e:
                logging.error(f"删除项目目录失败 {project_dir}: {str(e)}")
    
    annotation_project.remove(db, id=project_id)
    return {"message": "项目删除成功"}

@router.get("/projects/{project_id}/class-stats")
def get_project_class_stats(project_id: UUID, db: Session = Depends(get_db)):
    """每个类别的框数与图片数，以及复核状态分布（只读查看/定位问题用）"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    classes = list(project.classes or [])
    per_class = [{"class_id": i, "name": name, "boxes": 0, "images": 0} for i, name in enumerate(classes)]
    review = {}
    total = no_box = 0
    rows = db.query(ImageAnnotationModel.annotations, ImageAnnotationModel.review_status).filter(
        ImageAnnotationModel.project_id == project_id).all()
    for annotations, review_status in rows:
        total += 1
        review[review_status or "none"] = review.get(review_status or "none", 0) + 1
        seen = set()
        for ann in annotations or []:
            cid = ann.get("class_id") if isinstance(ann, dict) else None
            if isinstance(cid, int) and 0 <= cid < len(per_class):
                per_class[cid]["boxes"] += 1
                seen.add(cid)
        for cid in seen:
            per_class[cid]["images"] += 1
        no_box += not annotations
    return {"project_id": str(project_id), "total_images": total, "images_without_boxes": no_box,
            "classes": per_class, "review_status": review, "review_required": bool(project.review_required),
            "pipeline_run_id": str(project.pipeline_run_id) if project.pipeline_run_id else None}


@router.get("/projects/{project_id}/stats", response_model=ProjectStats)
def get_project_stats(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """获取项目统计信息"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    return annotation_project.get_project_stats(db, project_id=project_id)

@router.post("/projects/{project_id}/scan")
def scan_project_images(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """扫描项目图片"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    service = AnnotationService()
    image_directory_value = str(project.image_directory) if project.image_directory is not None else ""
    count = service.scan_images(db, project_id, image_directory_value)
    return {"message": f"扫描完成，发现 {count} 张图片"}

@router.get("/projects/{project_id}/images")
def get_project_images(
    project_id: UUID,
    skip: int = 0,
    limit: int = 50,
    order_by: str = "name",
    db: Session = Depends(get_db)
):
    """获取项目图片列表

    order_by: name(文件名) / created(扫描顺序) / updated(最近修改)
    默认按文件名排序，保证多人协作下顺序稳定。
    """
    return image_annotation.get_by_project_id(
        db, project_id=project_id, skip=skip, limit=limit, order_by=order_by
    )

@router.get("/images/{image_id}", response_model=ImageAnnotation)
def get_image_annotation(
    image_id: UUID,
    db: Session = Depends(get_db)
):
    """获取图片标注"""
    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    return image

@router.post("/images/{image_id}/lease", response_model=LeaseResponse)
def acquire_image_lease(
    image_id: UUID,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取或续期图片标注租约

    幂等：打开图片时调用一次，之后前端定时调用同一接口续期。
    图片被他人占用时返回 423；管理员可用 force=true 强制接管。
    """
    if force and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="只有管理员可以强制接管标注中的图片")

    image = _acquire_lease(db, image_id, current_user, force=force)
    return LeaseResponse(
        image_id=image.id,
        version=image.version,
        holder=LeaseHolder(
            user_id=current_user.id,
            username=current_user.username,
            locked_at=image.locked_at,
        ),
        expires_at=image.locked_at + ANNOTATION_LEASE_TTL,
    )

@router.delete("/images/{image_id}/lease")
def release_image_lease(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """释放图片标注租约（切换图片或关闭页面时调用）"""
    # 条件里限定 locked_by 为自己，避免误释放他人在租约过期后重新获取的锁
    db.execute(
        update(ImageAnnotationModel)
        .where(
            ImageAnnotationModel.id == image_id,
            ImageAnnotationModel.locked_by == current_user.id,
        )
        .values(
            locked_by=None,
            locked_at=None,
            updated_at=ImageAnnotationModel.updated_at,
        )
    )
    db.commit()
    return {"message": "租约已释放"}

@router.post("/projects/{project_id}/next", response_model=NextImageResponse)
def claim_next_image(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """认领下一张待标注图片

    跳过已完成和已被他人占用的图片。多人同时点"下一张"时，SKIP LOCKED 让每个人
    各自拿到不同的行，不必预先给标注员分配图片，也不需要冲突重试。
    """
    now = datetime.utcnow()
    image_id = db.execute(
        select(ImageAnnotationModel.id)
        .where(
            ImageAnnotationModel.project_id == project_id,
            # isnot(True) 而非 is_(False)：历史数据里 is_completed 可能为 NULL
            ImageAnnotationModel.is_completed.isnot(True),
            _lease_available(current_user.id, now),
        )
        .order_by(ImageAnnotationModel.image_name)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()

    if image_id is None:
        return NextImageResponse(message="没有待标注的图片")

    db.execute(
        update(ImageAnnotationModel)
        .where(ImageAnnotationModel.id == image_id)
        .values(
            locked_by=current_user.id,
            locked_at=now,
            updated_at=ImageAnnotationModel.updated_at,
        )
    )
    db.commit()

    return NextImageResponse(
        image=image_annotation.get(db, id=image_id),
        expires_at=now + ANNOTATION_LEASE_TTL,
    )

@router.get("/projects/{project_id}/presence", response_model=PresenceResponse)
def get_project_presence(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """项目内当前谁在标注哪张图（前端定时轮询，用于在图片列表上显示占用者）"""
    now = datetime.utcnow()
    rows = db.execute(
        select(
            ImageAnnotationModel.id,
            ImageAnnotationModel.image_name,
            User.id,
            User.username,
            ImageAnnotationModel.locked_at,
        )
        .join(User, User.id == ImageAnnotationModel.locked_by)
        .where(
            ImageAnnotationModel.project_id == project_id,
            ImageAnnotationModel.locked_at >= now - ANNOTATION_LEASE_TTL,
        )
    ).all()

    return PresenceResponse(entries=[
        PresenceEntry(
            image_id=row[0],
            image_name=row[1],
            user_id=row[2],
            username=row[3],
            locked_at=row[4],
        )
        for row in rows
    ])

@router.put("/images/{image_id}", response_model=ImageAnnotation)
def update_image_annotation(
    image_id: UUID,
    annotation_update: ImageAnnotationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新图片标注

    需持有租约（图片空闲时自动获取），并在客户端提供 expected_version 时做乐观锁校验。
    租约冲突返回 423，版本冲突返回 409 并附带最新数据，交由前端决定重新加载还是覆盖，
    绝不静默丢弃他人的标注。
    """
    update_data = annotation_update.dict(exclude_unset=True)
    expected_version = update_data.pop("expected_version", None)

    now = datetime.utcnow()
    conditions = [
        ImageAnnotationModel.id == image_id,
        _lease_available(current_user.id, now),
    ]
    if expected_version is not None:
        conditions.append(ImageAnnotationModel.version == expected_version)

    values = dict(update_data)
    values.update({
        "version": ImageAnnotationModel.version + 1,
        "last_edited_by": current_user.id,
        # 保存即续租，标注员连续编辑时无需依赖心跳
        "locked_by": current_user.id,
        "locked_at": now,
    })

    result = db.execute(
        update(ImageAnnotationModel).where(*conditions).values(**values)
    )
    db.commit()

    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")

    if result.rowcount == 0:
        if _lease_held_by_other(image, current_user.id, now):
            raise _lease_conflict(db, image)
        raise HTTPException(status_code=409, detail={
            "message": "该图片已被他人修改，请重新加载后再保存",
            "version": image.version,
            "annotations": image.annotations,
            "last_edited_by": _username(db, image.last_edited_by),
        })

    return image

@router.delete("/images/{image_id}")
def delete_image_annotation(
    image_id: UUID,
    db: Session = Depends(get_db)
):
    """删除图片"""
    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    image_annotation.remove(db, id=image_id)
    return {"message": "图片删除成功"}

@router.post("/projects/{project_id}/export")
def export_annotations(
    project_id: UUID,
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """导出标注数据"""
    from fastapi.responses import FileResponse
    import os
    
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    service = AnnotationService()
    temp_zip_path = service.export_annotations(db, project_id, export_request)
    
    # 返回文件下载响应
    filename = f"{project.name}_export.zip"
    
    # 添加清理任务
    def cleanup_file(file_path: str):
        try:
            os.unlink(file_path)
        except:
            pass
    
    background_tasks.add_task(cleanup_file, temp_zip_path)
    
    return FileResponse(
        path=temp_zip_path,
        filename=filename,
        media_type='application/zip'
    )

@router.post("/projects/upload")
def create_project_with_images(
    name: str = Form(...),
    description: str = Form(""),
    project_type: str = Form("detection"),
    classes: str = Form(None),  # 可选参数，因为当import_original_annotations为True时可能不需要
    class_keypoints: str = Form(None),  # 新增关键点配置参数
    import_original_annotations: bool = Form(False),
    images_zip: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """创建标注项目并上传图片ZIP"""
    import json
    
    # 根据import_original_annotations决定是否需要classes
    if not import_original_annotations:
        # 如果没勾选导入原标注，则classes是必需的
        if not classes:
            raise HTTPException(status_code=400, detail="类别列表是必需的")
        
        try:
            classes_list = json.loads(classes)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="类别数据格式错误")
    else:
        # 如果勾选了导入原标注，classes将从ZIP文件中解析
        classes_list = []
    
    # 解析关键点配置
    class_keypoints_config = None
    if class_keypoints:
        try:
            class_keypoints_config = json.loads(class_keypoints)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="关键点配置数据格式错误")
    
    if images_zip.filename and not images_zip.filename.endswith('.zip'): 
        raise HTTPException(status_code=400, detail="只支持ZIP文件")
    
    service = AnnotationService()
    project = service.create_project_with_zip_and_import(
        db=db,
        name=name,
        description=description,
        project_type=project_type,
        classes=classes_list,
        class_keypoints=class_keypoints_config,
        import_original_annotations=import_original_annotations,
        zip_file=images_zip
    )
    
    return project

@router.post("/projects/{project_id}/export-to-dataset")
def export_to_dataset(
    project_id: UUID,
    dataset_name: str = Form(...),
    dataset_description: str = Form(""),
    db: Session = Depends(get_db)
):
    """将标注项目导出为数据集"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    service = AnnotationService()
    new_dataset = service.export_to_dataset(db, project_id, dataset_name, dataset_description)
    return {"message": "导出为数据集成功", "dataset_id": new_dataset.id}

@router.post("/projects/upload-folder")
def create_project_with_folder(
    name: str = Form(...),
    description: str = Form(""),
    project_type: str = Form("detection"),
    classes: str = Form(...),
    import_original_annotations: bool = Form(False),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """从本地文件夹创建标注项目"""
    import json
    import tempfile
    import zipfile
    
    try:
        classes_list = json.loads(classes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="类别数据格式错误")
    
    # 创建临时ZIP文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for image_file in images:
                # 读取文件内容
                content = image_file.file.read()
                # 将文件添加到ZIP中
                filename_value = image_file.filename if image_file.filename is not None else "unknown"
                zipf.writestr(filename_value, content)
                # 重置文件指针
                image_file.file.seek(0)
        
        temp_zip_path = temp_zip.name
    
    # 使用临时ZIP文件创建项目
    try:
        with open(temp_zip_path, 'rb') as f:
            # 创建UploadFile对象
            zip_upload = UploadFile(filename=f"{name}.zip", file=f)
            
            service = AnnotationService()
            project = service.create_project_with_zip_and_import(
                db=db,
                name=name,
                description=description,
                project_type=project_type,
                classes=classes_list,
                import_original_annotations=import_original_annotations,
                zip_file=zip_upload
            )
            
            return project
    
    finally:
        # 清理临时文件
        import os
        try:
            os.unlink(temp_zip_path)
        except:
            pass

@router.get("/browse-directories", dependencies=[Depends(forbid_in_external_mode)])
def browse_directories(path: str = ""): 
    """浏览本地目录"""
    import os
    import platform
    from pathlib import Path
    
    # 如果没有提供路径，返回根目录列表
    if not path:
        if platform.system() == "Windows":
            # Windows: 返回所有驱动器
            drives = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path):
                    drives.append({
                        "name": f"{letter}:",
                        "path": drive_path,
                        "type": "drive",
                        "is_directory": True
                    })
            return {"items": drives, "current_path": ""}
        else:
            # Linux/Mac: 从根目录开始
            path = "/"
    
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            raise HTTPException(status_code=404, detail="路径不存在")
        
        if not path_obj.is_dir():
            raise HTTPException(status_code=400, detail="不是有效的目录")
        
        items = []
        
        # 添加上级目录（除非是根目录）
        if path_obj.parent != path_obj:
            items.append({
                "name": "..",
                "path": str(path_obj.parent),
                "type": "parent",
                "is_directory": True
            })
        
        # 列出目录内容
        try:
            for item in sorted(path_obj.iterdir()):
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory",
                        "is_directory": True
                    })
        except PermissionError:
            raise HTTPException(status_code=403, detail="没有权限访问此目录")
        
        return {
            "items": items,
            "current_path": str(path_obj)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"浏览目录失败: {str(e)}")

@router.get("/scan-directory-images", dependencies=[Depends(forbid_in_external_mode)])
def scan_directory_images(directory_path: str):
    """扫描目录中的图片数量"""
    from pathlib import Path
    
    try:
        path_obj = Path(directory_path)
        if not path_obj.exists():
            raise HTTPException(status_code=404, detail="目录不存在")
        
        if not path_obj.is_dir():
            raise HTTPException(status_code=400, detail="不是有效的目录")
        
        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}
        
        image_count = 0
        image_files = []
        
        try:
            for item in path_obj.iterdir():
                if item.is_file() and item.suffix.lower() in image_extensions:
                    image_count += 1
                    image_files.append({
                        "name": item.name,
                        "path": str(item),
                        "size": item.stat().st_size
                    })
                    
                    # 只返回前10个文件作为预览
                    if len(image_files) >= 10:
                        break
        
        except PermissionError:
            raise HTTPException(status_code=403, detail="没有权限访问此目录")
        
        return {
            "directory_path": directory_path,
            "image_count": image_count,
            "sample_images": image_files,
            "is_valid": image_count > 0
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描目录失败: {str(e)}")

@router.get("/projects/{project_id}/images/{image_id}/file")
def get_image_file(
    project_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db)
):
    """获取图片文件"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    # 获取项目信息
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    # 获取图片信息
    image = image_annotation.get(db, id=image_id)
    # 检查image是否存在
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    
    # 获取实际的project_id值
    image_project_id = image.project_id if image.project_id is not None else UUID('00000000-0000-0000-0000-000000000000')
    if str(image_project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="图片未找到")
    
    # 构建图片文件路径
    image_path_str = str(image.image_path) if image.image_path is not None else ""
    image_name_str = str(image.image_name) if image.image_name is not None else ""
    image_directory_str = str(project.image_directory) if project.image_directory is not None else ""
    
    logging.info(f"get_image_file: image_path={image_path_str}, image_name={image_name_str}, project_directory={image_directory_str}")
    
    image_file_path = None
    
    if image_path_str.startswith('datasets/'):
        # 如果路径已经包含datasets，直接使用
        image_file_path = Path("app/static") / image_path_str
        logging.info(f"get_image_file: Using datasets path: {image_file_path}")
    elif Path(image_path_str).is_absolute():
        # 如果是绝对路径，直接使用
        image_file_path = Path(image_path_str)
        logging.info(f"get_image_file: Using absolute path: {image_file_path}")
    else:
        # 首先检查image_path是否只包含文件名（没有路径分隔符）
        if Path(image_path_str).name == image_path_str:
            # 如果image_path只包含文件名，则使用项目的image_directory和image_path组合
            # 注意：这里使用image_path而不是image_name，因为两者应该是相同的
            if image_directory_str and image_path_str:
                # 修复Windows路径问题：规范化路径分隔符
                image_file_path = Path(image_directory_str) / image_path_str
                # 尝试使用os.path.normpath来处理跨平台路径
                import os
                normalized_path = os.path.normpath(str(image_file_path))
                image_file_path = Path(normalized_path)
                logging.info(f"get_image_file: Using project_dir + image_path: {image_file_path}")
        else:
            # 否则先尝试直接使用image_path作为相对路径
            image_file_path = Path(image_path_str)
            logging.info(f"get_image_file: Using direct image_path: {image_file_path}")
            
        # 如果文件不存在，尝试使用项目的image_directory和image_path组合
        if not image_file_path or not image_file_path.exists():
            image_path_str_fallback = str(image.image_name) if image.image_name is not None else ""
            if image_directory_str and image_path_str_fallback:
                # 修复Windows路径问题：规范化路径分隔符
                fallback_path = Path(image_directory_str) / image_path_str_fallback
                import os
                normalized_fallback_path = os.path.normpath(str(fallback_path))
                fallback_path = Path(normalized_fallback_path)
                logging.info(f"get_image_file: Trying fallback path: {fallback_path}")
                if fallback_path.exists():
                    image_file_path = fallback_path
                else:
                    logging.info(f"get_image_file: Fallback path does not exist")
    
    if not image_file_path or not image_file_path.exists():
        logging.info(f"get_image_file: Final path does not exist: {image_file_path}")
        raise HTTPException(status_code=404, detail="图片文件不存在")
    else:
        logging.info(f"get_image_file: Final path exists: {image_file_path}")
    
    return FileResponse(image_file_path)

@router.post("/images/{image_id}/auto-annotate")
def auto_annotate_image(
    image_id: UUID,
    model_id: str = Body(...),
    confidence: float = Body(0.25),
    iou: float = Body(0.45),
    overwrite: bool = Body(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """使用AI模型自动标注图片"""
    from app.services.annotation_service import AnnotationService
    import uuid

    # 验证model_id格式
    try:
        # 尝试将model_id转换为UUID对象
        uuid.UUID(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="模型ID格式无效，请使用有效的UUID格式")

    # 自动标注会覆写标注内容，与手工保存一样需要先持有租约。
    # 记录调用前是否已持有：批量自动标注不该把整个项目的图片都锁住 5 分钟，
    # 因此标注完成后要把这类临时租约还回去。
    existing = image_annotation.get(db, id=image_id)
    if not existing:
        raise HTTPException(status_code=404, detail="图片未找到")
    lease_held_before = existing.locked_by == current_user.id

    image = _acquire_lease(db, image_id, current_user)

    # 获取模型信息
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    # 获取项目信息
    project = annotation_project.get(db, id=image.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    try:
        service = AnnotationService()
        project_classes_value = project.classes if project.classes is not None else []
        project_classes_final = project_classes_value if isinstance(project_classes_value, list) else []
        
        annotations = service.auto_annotate_image(
                db=db,
                image_id=image_id,
                model_path=str(db_model.path) if db_model.path is not None else "",
                project_classes=project_classes_final,
                model_type=db_model.type if db_model.type else "",
                project_type=project.project_type if project.project_type else "detection",
                confidence=confidence,
                iou=iou,
                overwrite=overwrite
            )

        # 服务层直接写库，这里补上版本自增，否则前端拿着旧版本号保存时
        # 会以为期间无人改动，把自动标注的结果覆盖掉
        lease_values = {
            "version": ImageAnnotationModel.version + 1,
            "last_edited_by": current_user.id,
        }
        if not lease_held_before:
            # 归还临时租约，让其他标注员可以立刻接手这张图
            lease_values.update({"locked_by": None, "locked_at": None})

        db.execute(
            update(ImageAnnotationModel)
            .where(ImageAnnotationModel.id == image_id)
            .values(**lease_values)
        )
        db.commit()

        return {
            "success": True,
            "message": "自动标注完成",
            "annotations": annotations,
            "annotation_count": len(annotations),
            "version": image_annotation.get(db, id=image_id).version
        }
        
    except HTTPException as e:
        # 重新抛出HTTPException，保持原始状态码和详细信息
        raise
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"依赖库安装失败: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"文件未找到: {str(e)}")
    except Exception as e:
        # 捕获其他所有异常，提供更详细的错误信息
        import traceback
        traceback_str = traceback.format_exc()
        logging.error(f"自动标注失败: {traceback_str}")
        raise HTTPException(status_code=500, detail=f"自动标注失败: {str(e)}")



@router.post("/projects/{project_id}/mark-all-completed")
def mark_all_completed(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """一键标记所有图片为已完成"""
    # 获取项目信息
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    if project.review_required:
        # 流水线项目以逐帧复核状态为准，一键全部完成等于绕过复核
        raise HTTPException(status_code=403, detail="该项目来自自动训练流水线，需在“流水线任务中心”逐帧复核或放行，不能一键全部完成")

    try:
        total_count = db.query(func.count(ImageAnnotationModel.id)).filter(
            ImageAnnotationModel.project_id == project_id
        ).scalar() or 0

        # 单条批量 UPDATE 并自增版本号：正打开这些图片的标注员保存时会收到 409
        # 提示重新加载，而不是用手里的旧状态把完成标记覆盖回去
        result = db.execute(
            update(ImageAnnotationModel)
            .where(
                ImageAnnotationModel.project_id == project_id,
                ImageAnnotationModel.is_completed.isnot(True),
            )
            .values(
                is_completed=True,
                version=ImageAnnotationModel.version + 1,
                last_edited_by=current_user.id,
            )
        )
        db.commit()

        return {
            "success": True,
            "message": f"已标记 {result.rowcount} 张图片为完成",
            "updated_count": result.rowcount,
            "total_count": total_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标记失败: {str(e)}")


@router.post("/projects/{project_id}/import-annotations")
def import_project_annotations(
    project_id: UUID,
    overwrite: bool = Form(False),
    db: Session = Depends(get_db)
):
    """为已存在的项目补导入磁盘上的 YOLO 标签

    建项目时没勾"导入原标注"（服务器目录模式下以前根本勾不上），
    图片记录会全是空标注，但盘上的 labels/*.txt 一直都在。
    这个接口用来事后补上，不必删掉项目重建。

    overwrite 默认 False：只填补当前没有标注的图片，不覆盖已标好的内容。
    """
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")

    service = AnnotationService()
    stats = service.import_annotations_from_disk(
        db, project_id, overwrite=overwrite)
    return {"message": "导入完成", **stats}


# 扩展数据功能
@router.post("/projects/{project_id}/expand-data")
async def expand_annotation_project(
    project_id: UUID,
    import_original_annotations: bool = Form(...),
    zip_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """为现有标注项目扩展数据"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    service = AnnotationService()
    result = service.expand_project_data(
        db=db,
        project_id=project_id,
        import_original_annotations=import_original_annotations,
        zip_file=zip_file
    )
    
    return result


@router.post("/merge-projects")
def merge_annotation_projects(
    request: MergeProjectsRequest,
    db: Session = Depends(get_db)
):
    """合并多个标注项目"""
    service = AnnotationService()
    return service.merge_projects(
        db=db,
        target_project_name=request.target_project_name,
        source_project_ids=request.source_project_ids,
        delete_source_projects=request.delete_source_projects,
        duplicate_handling=request.duplicate_handling
    )

