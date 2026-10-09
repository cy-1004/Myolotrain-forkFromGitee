import threading
import time
from typing import Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.user import get_user_by_username
from app.db.session import SessionLocal, get_db
from app.models.user import User, UserRole
from app.schemas.user import TokenData

# 从配置读取（.env 或同名环境变量均可）。注意不能直接用 os.environ 读 .env：
# pydantic 只把 .env 加载进 Settings，不会写回进程环境变量。
SECRET_KEY = settings.SECRET_KEY
if settings.EXTERNAL_MODE and len(SECRET_KEY) < 32:
    # 对外部署时随机密钥的后果（每次重启全员登出）不可接受，弱密钥则可被暴力破解伪造令牌，直接拒绝启动
    raise RuntimeError(
        "EXTERNAL_MODE=true 时必须在 .env 中配置至少 32 位的 SECRET_KEY，"
        "生成方法：python -c \"import secrets;print(secrets.token_urlsafe(48))\""
    )
if not SECRET_KEY:
    # 未配置时生成临时密钥，仅供本地开发；重启即失效，所有用户需重新登录
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)
    print(f"警告: 使用临时生成的JWT密钥，请在生产环境中设置环境变量'SECRET_KEY'")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# OAuth2密码Bearer令牌方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """获取当前管理员用户"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

# ---------------------------------------------------------------------
# 控制台统一鉴权
#
# 控制台前端有两种带凭据的方式：authenticatedFetch 带 Authorization 头；
# 另有不少脚本直接 fetch、以及 <img>/<a>/window.open 加载的图片和下载链接，只能靠
# 登录页写入的 access_token Cookie。因此这里两种都接受，头优先。
# ---------------------------------------------------------------------
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def extract_token(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """取出请求携带的 JWT，返回 (token, 来源)；来源为 "header" / "cookie" / None"""
    scheme, param = get_authorization_scheme_param(request.headers.get("Authorization"))
    if scheme.lower() == "bearer" and param:
        return param, "header"
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token, "cookie"
    return None, None


def _same_origin(request: Request) -> bool:
    """Cookie 鉴权的写请求必须来自本站页面（防 CSRF）

    SameSite=Lax 已挡住了大部分跨站 POST，这里再校验一次 Origin/Referer 作为兜底。
    两者都没有时放行：浏览器发起的跨源写请求一定带 Origin，没有说明不是浏览器跨站场景。
    """
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        return True
    source_host = urlsplit(source).netloc.lower()
    allowed = {h.lower() for h in (request.headers.get("host"), request.headers.get("x-forwarded-host")) if h}
    return source_host in allowed


def require_console_user(request: Request, db: Session = Depends(get_db)) -> User:
    """控制台接口的统一鉴权依赖：登录用户（Bearer 头或 Cookie），且账号未停用"""
    token, source = extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if source == "cookie" and request.method not in _SAFE_METHODS and not _same_origin(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-site request rejected")
    user = get_current_user(db=db, token=token)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return user


def require_console_admin(current_user: User = Depends(require_console_user)) -> User:
    """仅管理员可用的控制台接口"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user


# 静态数据文件（数据集图片、模型、抽帧结果等）的鉴权缓存。
# 标注页、网格预览一屏就有上百张图，每张都查一次用户表太浪费，这里按用户名缓存
# "存在且未停用"的结论一小段时间；停用账号最多延迟这么久失去静态文件访问权限。
_STATIC_AUTH_TTL_SECONDS = 60
_static_auth_cache: dict = {}
_static_auth_lock = threading.Lock()


def is_token_valid_for_static(token: str) -> bool:
    """校验访问静态数据文件的令牌：签名与有效期 + 账号存在且未停用（带缓存）"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return False
    username = payload.get("sub")
    if not username:
        return False

    now = time.monotonic()
    with _static_auth_lock:
        cached = _static_auth_cache.get(username)
        if cached and cached[1] > now:
            return cached[0]

    db = SessionLocal()
    try:
        user = get_user_by_username(db, username=username)
        valid = bool(user and user.is_active)
    finally:
        db.close()

    with _static_auth_lock:
        _static_auth_cache[username] = (valid, now + _STATIC_AUTH_TTL_SECONDS)
    return valid


def forbid_in_external_mode() -> None:
    """对外部署模式下禁用的接口：浏览/打开服务器本地文件系统、按任意服务器路径导入数据

    这类接口在内网单机使用时很方便，但对外暴露等于把整台服务器（容器）的文件系统交给调用方。
    对外部署时数据一律通过上传进入平台。
    """
    if settings.EXTERNAL_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该功能需要访问服务器本地文件系统，对外部署模式（EXTERNAL_MODE=true）下已禁用，请改用上传",
        )
