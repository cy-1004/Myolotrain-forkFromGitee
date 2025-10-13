import logging
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from app.db.session import Base, engine, SessionLocal
from app.core.config import settings
from app.crud.user import get_user_by_username, create_user
from app.schemas.user import UserCreate
from app.models.user import UserRole

# 导入所有模型以确保它们被注册
from app.models import Dataset, Model, TrainingTask, DetectionTask, AnnotationProject, ImageAnnotation, User

logger = logging.getLogger(__name__)

def create_initial_admin():
    """创建初始管理员用户"""
    db = SessionLocal()
    try:
        # 检查是否已存在管理员用户
        admin_user = get_user_by_username(db, username="admin")
        if not admin_user:
            # 创建初始管理员用户
            # 确保密码不超过72字节（bcrypt限制）
            admin_password = "admin@123"  # 默认密码，用户应首次登录后修改
            if len(admin_password.encode('utf-8')) > 72:
                admin_password = admin_password.encode('utf-8')[:72].decode('utf-8', 'ignore')
            user_in = UserCreate(
                username="admin",
                password=admin_password,
                confirm_password=admin_password,
                role=UserRole.ADMIN
            )
            admin_user = create_user(db=db, user=user_in)
            logger.info("Initial admin user created successfully")
        else:
            logger.info("Admin user already exists")
    finally:
        db.close()

def init_db():
    try:
        # 测试数据库连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")

        # 检查模型是否注册
        logger.info(f"Registered models: {Base.metadata.tables.keys()}")

        # 创建表
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Tables in database: {tables}")

        # 检查每个表的列
        for table in tables:
            columns = [col['name'] for col in inspector.get_columns(table)]
            logger.info(f"Columns in {table}: {columns}")

        # 检查并添加缺失的列
        if 'training_tasks' in tables:
            columns = [col['name'] for col in inspector.get_columns('training_tasks')]
            if 'process_id' not in columns:
                logger.info("Adding process_id column to training_tasks table")
                with engine.connect() as conn:
                    conn.execute(text("""
                        ALTER TABLE training_tasks
                        ADD COLUMN process_id VARCHAR(255)
                    """))
                    conn.commit()
                logger.info("Added process_id column to training_tasks table")

        # 检查并修改 detection_tasks 表的 input_path 列
        if 'detection_tasks' in tables:
            # 检查 input_path 列是否为非空
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'detection_tasks' AND column_name = 'input_path'
                """))
                column_info = result.fetchone()
                if column_info and column_info[1] == 'NO':  # 'NO' 表示不可为空
                    logger.info("Modifying input_path column in detection_tasks table to allow NULL values")
                    conn.execute(text("""
                        ALTER TABLE detection_tasks
                        ALTER COLUMN input_path DROP NOT NULL
                    """))
                    conn.commit()
                    logger.info("Modified input_path column in detection_tasks table to allow NULL values")

        # 检查并添加 datasets 表的 is_external 列
        if 'datasets' in tables:
            # 检查 is_external 列是否存在
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'datasets' AND column_name = 'is_external'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding is_external column to datasets table")
                    conn.execute(text("""
                        ALTER TABLE datasets
                        ADD COLUMN is_external BOOLEAN DEFAULT FALSE
                    """))
                    conn.commit()
                    logger.info("Added is_external column to datasets table")

        # 检查并添加 users 表的所有必要列
        if 'users' in tables:
            with engine.connect() as conn:
                # 检查并添加 password 列
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'password'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding password column to users table")
                    
                    # 首先检查是否有任何用户行存在
                    user_count_result = conn.execute(text("SELECT COUNT(*) FROM users"))
                    user_count = user_count_result.scalar()
                    
                    if user_count > 0:
                        # 如果有用户行，先添加一个可为NULL的字段
                        conn.execute(text("""
                            ALTER TABLE users
                            ADD COLUMN password VARCHAR(255)
                        """))
                        # 然后为现有用户设置默认密码（会被哈希处理）
                        from app.crud.user import get_password_hash
                        default_password = 'default_password'
                        hashed_default_password = get_password_hash(default_password)
                        conn.execute(text("""
                            UPDATE users
                            SET password = :password
                        """), {'password': hashed_default_password})
                        # 最后设置为NOT NULL
                        conn.execute(text("""
                            ALTER TABLE users
                            ALTER COLUMN password SET NOT NULL
                        """))
                    else:
                        # 如果没有用户行，可以直接添加NOT NULL字段
                        conn.execute(text("""
                            ALTER TABLE users
                            ADD COLUMN password VARCHAR(255) NOT NULL
                        """))
                    
                    conn.commit()
                    logger.info("Added password column to users table")
                
                # 检查并添加 role 列
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'role'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding role column to users table")
                    conn.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'operator'
                    """))
                    conn.commit()
                    logger.info("Added role column to users table")
                
                # 检查并添加 is_active 列
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'is_active'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding is_active column to users table")
                    conn.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE
                    """))
                    conn.commit()
                    logger.info("Added is_active column to users table")
                
                # 检查并添加 created_at 列
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'created_at'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding created_at column to users table")
                    conn.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    """))
                    conn.commit()
                    logger.info("Added created_at column to users table")
                
                # 检查并添加 updated_at 列
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'updated_at'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding updated_at column to users table")
                    conn.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    """))
                    conn.commit()
                    logger.info("Added updated_at column to users table")
                
                # 检查并添加 last_login 列
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'last_login'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding last_login column to users table")
                    conn.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN last_login TIMESTAMP
                    """))
                    conn.commit()
                    logger.info("Added last_login column to users table")

        # 创建初始管理员用户
        create_initial_admin()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise
