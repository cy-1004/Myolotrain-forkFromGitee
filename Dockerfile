FROM python:3.12-slim

# 配置apt使用国内镜像源
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list
RUN sed -i 's/security.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 配置pip使用国内镜像源
RUN mkdir -p /root/.pip
RUN echo "[global]\n\
index-url = https://pypi.tuna.tsinghua.edu.cn/simple\n\
trusted-host = pypi.tuna.tsinghua.edu.cn" > /root/.pip/pip.conf

# 复制依赖文件并安装
COPY requirements.txt .
# 安装基础依赖，并添加CPU版本的onnxruntime 1.21.0
RUN pip install --no-cache-dir -r requirements.txt onnxruntime==1.21.0

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p app/static/uploads app/static/datasets app/static/models app/static/results app/static/annotations logs/tensorboard

# 暴露端口
EXPOSE 8000 6006

# 启动命令
CMD ["python", "run.py"]