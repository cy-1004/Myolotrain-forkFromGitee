# Docker 部署指南

部署形态：`app`（平台）+ `db`（PostgreSQL）两个容器，**对外只开放一个端口**，API 与控制台共用。
数据库不对外暴露；所有运行数据（数据集、模型、抽帧结果、训练日志）都在 `appdata` 数据卷里，镜像只包含代码。

## 1. 系统要求

| 项目 | 要求 |
|---|---|
| 系统 | Linux x86_64（推荐 Ubuntu 22.04+）；Windows 10/11 + Docker Desktop（WSL2 后端）可用于测试 |
| Docker | Docker Engine 24+，自带 `docker compose`（v2） |
| GPU（可选） | NVIDIA 驱动 ≥ 535（推荐 ≥ 560）+ nvidia-container-toolkit。没有 GPU 也能运行，训练会用 CPU |
| 磁盘 | 镜像约 10 GB；数据卷按数据量预留，建议 ≥ 100 GB |
| 内存 | ≥ 16 GB（训练时 DataLoader 还会用到共享内存，compose 中已设 `shm_size: 8gb`） |

## 2. 安装 NVIDIA Container Toolkit（使用 GPU 时）

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 验证：能看到 GPU 列表即可
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi
```

Windows + Docker Desktop 只需在 Windows 侧装好 NVIDIA 驱动，无需额外安装。

## 3. 配置

```bash
cp .env.example .env
```

至少填写：

| 配置项 | 说明 |
|---|---|
| `SECRET_KEY` | 登录令牌签名密钥，≥ 32 位，未配置时容器拒绝启动。生成：`python3 -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `POSTGRES_PASSWORD` | 数据库密码（只在 compose 内部网络使用） |
| `ADMIN_INITIAL_PASSWORD` | 可选。首次启动创建 `admin` 账号的密码；留空则随机生成，**只在首次启动日志里打印一次** |
| `APP_PORT` | 首选对外端口，默认 8000。被占用时自动顺延，见第 4 节 |

其余配置项的含义见 `.env.example` 中的注释。

## 4. 构建与启动

```bash
docker compose build
scripts/start.sh            # Windows：powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

启动脚本做的事：

1. **自动判断 GPU**：检测到 NVIDIA 驱动和 Docker 的 NVIDIA 运行时就叠加 `docker-compose.gpu.yml`；可用 `USE_GPU=true/false` 强制指定。
2. **端口被占用时自动顺延**：首选 `APP_PORT`（默认 8000），被其他程序占用就试 8001、8002……，最多 `APP_PORT_MAX_TRIES` 个（默认 20）。
   - 实际端口记录在 `.app_port`。下次启动只要 `APP_PORT` 没改，就优先沿用上次的端口，保证接口调用方的地址不变；
   - 本服务自己的容器占着的端口不算冲突，重复执行脚本不会换端口；
   - 不希望顺延时设 `APP_PORT_STRICT=true`，冲突直接报错退出（防火墙/网关已固定端口的环境）；
   - 端口与首选/上次不同时会醒目提示——调用方和 `PUBLIC_BASE_URL` 需要同步使用新端口。
3. 打印访问地址，并等待服务就绪（`/api/health`）；首次启动要初始化数据库，可能需要一两分钟。

输出示例：

```
端口 8000 已被占用
使用端口 8001 启动...
============================================================
注意：端口 8000 被占用，本次使用端口 8001
      接口调用方和 PUBLIC_BASE_URL 需要使用新端口
控制台:   http://10.0.0.5:8001/
健康检查: http://10.0.0.5:8001/api/health
实际端口已记录到 .app_port
============================================================
等待服务就绪...... 已就绪
```

不用脚本、手动启动也可以（不会自动顺延端口）：

```bash
APP_PORT=8000 docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

## 5. 验证

```bash
docker compose ps                                     # 两个容器都是 healthy
curl -s http://127.0.0.1:<端口>/api/ready              # 数据库、数据目录、GPU 状态
docker compose exec app python -c "import torch;print(torch.cuda.is_available())"
docker compose exec app python tools/smoke_export.py  # TFLite 转换链路冒烟测试，输出 [PASS]
```

首次登录用 `admin` 和第 3 节的初始密码（或首次启动日志里打印的随机密码：`docker compose logs app | grep 初始密码`），登录后立即修改。

## 6. 对外部署模式（镜像默认开启）

镜像默认 `EXTERNAL_MODE=true`，与本地开发相比有这些差异：

- 所有控制台接口和 `/static` 下的数据文件都要求登录；
- 禁用浏览服务器文件系统、按服务器路径导入数据、打开日志文件夹等功能（数据一律通过上传进入平台）；
- 500 错误不再回显异常原文，响应里带 `request_id`，凭它在日志中定位：`docker compose logs app | grep <request_id>`；
- 不提供控制台内部接口的 `/docs`；
- 不启动 TensorBoard（它要单独占一个端口），训练曲线在“训练日志”弹窗里查看。

## 7. 数据与运维

**数据位置**：`appdata` 卷挂载到容器的 `/data`，旧代码写死的 `app/static/<数据目录>`、`logs/` 在容器里都是指向它的软链；数据库在 `pgdata` 卷。

**查看日志**：`docker compose logs -f app`

**升级**：

```bash
git pull
docker compose build
scripts/start.sh
```

**备份**：

```bash
docker compose exec db pg_dump -U postgres yolov8_platform > backup.sql
docker run --rm -v myolotrain_appdata:/data -v "$PWD":/backup alpine tar czf /backup/appdata.tgz -C /data .
```

**从已有的本地（Windows）环境迁移数据**：

1. 导出旧数据库：`pg_dump -U postgres yolov8_platform > old.sql`，导入到容器：
   `docker compose exec -T db psql -U postgres yolov8_platform < old.sql`
2. 把旧项目的 `app/static/` 下的数据目录拷进数据卷的 `static/` 下，例如：
   `docker run --rm -v myolotrain_appdata:/data -v /path/to/old/app/static:/src alpine sh -c "cp -a /src/datasets /src/models /src/annotations /data/static/"`
3. 旧数据库里存的是旧机器上的绝对路径（如 `C:\workspace\Myolotrain\app\static\...`）。在 `.env` 中配置旧项目根目录，读取时会自动映射到容器内的路径：
   `LEGACY_PATH_PREFIXES=["C:\\workspace\\Myolotrain"]`
4. 重启：`scripts/start.sh`

## 8. 反向代理（可选）

前面加 nginx 等反向代理时：

- 代理到 `http://<宿主机>:<.app_port 中的端口>`，或把代理也放进 compose 网络直接代理 `app:8000`；
- 设置 `FORWARDED_ALLOW_IPS=<代理的 IP>`，平台才会信任代理传来的 `X-Forwarded-*`；
- 设置 `PUBLIC_BASE_URL=https://你的域名`，webhook 等需要绝对链接的地方会用它；
- 上传大视频时调大代理的请求体限制（nginx：`client_max_body_size 4g;`）和超时。

## 9. 常见问题

| 现象 | 处理 |
|---|---|
| 容器启动后立即退出，日志提示 SECRET_KEY | `.env` 中设置 ≥ 32 位的 `SECRET_KEY` |
| `could not select device driver "nvidia"` | 未安装 nvidia-container-toolkit；安装后重启 Docker，或 `USE_GPU=false` 用 CPU 运行 |
| 训练时报 `bus error` / DataLoader 崩溃 | 共享内存不足，调大 compose 中的 `shm_size` |
| 端口全部被占用 | 释放端口，或调大 `APP_PORT_MAX_TRIES`，或修改 `APP_PORT` |
| 页面能打开但图片/模型 401 | 登录已过期，重新登录 |
| 迁移后旧数据集/模型找不到文件 | 检查第 7 节的数据拷贝位置和 `LEGACY_PATH_PREFIXES` |
| 容器重启后训练任务显示“已中断” | 训练进程随容器一起被终止，在训练列表点“继续训练”从 last.pt 续训 |
