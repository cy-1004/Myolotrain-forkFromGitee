# syntax=docker/dockerfile:1
# =====================================================================
# Myolotrain 平台镜像（GPU）。CPU-only 环境同样可用：没有 GPU 时 torch 自动回退 CPU。
#
# 构建：docker compose build            （或 docker build -t myolotrain .）
# 启动：scripts/start.sh / scripts/start.ps1   （宿主机端口被占用时自动顺延）
#
# 宿主机要求：NVIDIA 驱动 ≥ 535（推荐 ≥ 560）+ nvidia-container-toolkit。
# torch 的 cu126 wheel 自带 CUDA/cuDNN 用户态库，基础镜像不需要 nvidia/cuda。
# =====================================================================

ARG PYTHON_IMAGE=python:3.12-slim-bookworm

# ---------------------------------------------------------------------
# 构建阶段：编译工具只留在这一层（onnx2tf 依赖的 onnxsim 在部分平台需要源码编译）
# ---------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

# 国内镜像源；海外构建时传 --build-arg APT_MIRROR= --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG APT_MIRROR=mirrors.ustc.edu.cn
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL}

RUN if [ -n "$APT_MIRROR" ]; then sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; fi \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential cmake git \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# 先单独装 torch（来自 PyTorch 官方 CUDA 索引），再装其余依赖；
# constraints.txt 锁定的是在开发环境中验证过可以一起工作的版本组合（torch/TF/onnx2tf/ultralytics）
COPY requirements.txt constraints.txt /tmp/
RUN pip install --upgrade pip wheel \
 && pip install --index-url ${TORCH_INDEX_URL} "torch==2.6.0" "torchvision==0.21.0" \
 && pip install -r /tmp/requirements.txt -c /tmp/constraints.txt \
 && pip install -c /tmp/constraints.txt onnxruntime

# ---------------------------------------------------------------------
# 运行阶段
# ---------------------------------------------------------------------
FROM ${PYTHON_IMAGE}

ARG APT_MIRROR=mirrors.ustc.edu.cn
# 预置到镜像里的权重。离线部署必须预置；构建机无法访问 GitHub 时，
# 可先把同名 .pt 文件放进 docker/weights/，构建时优先使用本地文件
ARG BAKE_WEIGHTS="yolo11n.pt yolo11s.pt yolov8n.pt sam2.1_b.pt"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

# libgl1/libglib2.0-0：opencv-python 运行时依赖；procps：训练进程检查用到 ps；tini：转发信号、回收僵尸进程
RUN if [ -n "$APT_MIRROR" ]; then sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; fi \
 && apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 procps curl tini \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app

COPY --from=builder /opt/venv /opt/venv

# 预置权重：优先使用 docker/weights/ 下的本地文件，没有才下载
COPY docker/weights/ /tmp/weights/
COPY docker/bake_weights.sh /tmp/bake_weights.sh
RUN sh /tmp/bake_weights.sh /opt/weights ${BAKE_WEIGHTS} \
 && rm -rf /tmp/weights /tmp/bake_weights.sh \
 && chown -R app:app /opt/weights

# 平台配置：对外部署模式、数据与权重目录、单端口（不启动 TensorBoard）。
# 必须放在权重下载之后：YOLO_OFFLINE 会让下载失败，YOLO_CONFIG_DIR 会在 /data 下留下 root 属主的文件
ENV EXTERNAL_MODE=true \
    DATA_DIR=/data \
    WEIGHTS_DIR=/opt/weights \
    TENSORBOARD_ENABLED=false \
    TENSORBOARD_LOGS_DIR=/data/logs/tensorboard \
    SERVER_PORT=8000 \
    YOLO_CONFIG_DIR=/data/ultralytics \
    YOLO_AUTOINSTALL=false \
    YOLO_OFFLINE=true \
    TF_CPP_MIN_LOG_LEVEL=2 \
    FORWARDED_ALLOW_IPS=127.0.0.1
# 说明：
#   YOLO_AUTOINSTALL/YOLO_OFFLINE —— 禁止 Ultralytics 运行时自动 pip install / 联网，离线环境下会卡住或失败
#   FORWARDED_ALLOW_IPS —— 只信任本机反向代理传来的 X-Forwarded-*；前面有独立 nginx 等代理时改成代理的 IP

WORKDIR /app
COPY --chown=app:app . /app
# 去掉可能混入的 CRLF（Windows 上检出、未遵守 .gitattributes 时），否则 shebang 失效
RUN sed -i 's/\r$//' /app/docker/*.sh \
 && chmod +x /app/docker/entrypoint.sh \
 && mkdir -p /data && chown app:app /data

# 构建期冒烟测试：核心依赖都能导入（TFLite 转换链路的完整验证见 tools/smoke_export.py）
RUN python -c "import torch, torchvision, cv2, ultralytics, onnx, onnx2tf, tensorflow, fastapi, sqlalchemy, psycopg2; print('deps ok, torch', torch.__version__, 'ultralytics', ultralytics.__version__)"

USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker/entrypoint.sh"]
# 单 worker、不热重载：编排器和训练监控是进程内线程，多 worker 会重复执行
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
