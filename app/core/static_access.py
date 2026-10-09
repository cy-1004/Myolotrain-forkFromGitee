"""/static 下哪些路径无需登录即可访问

app/static 下除了前端代码，还有数据集图片、模型权重、抽帧结果等全部运行数据，
这些必须登录才能访问（鉴权中间件见 app/main.py）。
"""
import posixpath

# 前端代码目录，无需登录（登录页本身就要用到）
PUBLIC_STATIC_PREFIXES = ("/static/css/", "/static/js/", "/static/libs/", "/static/fonts/", "/static/templates/")


def is_static_path(path: str) -> bool:
    return path == "/static" or path.startswith("/static/")


def is_public_static(path: str) -> bool:
    """判断 /static 下的请求路径是否属于无需登录的前端资源"""
    # 必须先规范化：StaticFiles 会解析 ".."（Windows 上还把反斜杠当分隔符），
    # 不规范化的话 /static/js/../datasets/x 能以"前端代码"的名义读到数据文件
    normalized = posixpath.normpath(path.replace("\\", "/"))
    if normalized.startswith(PUBLIC_STATIC_PREFIXES):
        return True
    # 顶层页面外壳（login.html、annotation.html 等）：不含数据，页面加载后自己再检查登录
    rest = normalized[len("/static/"):] if normalized.startswith("/static/") else ""
    return bool(rest) and "/" not in rest and rest.endswith(".html")
