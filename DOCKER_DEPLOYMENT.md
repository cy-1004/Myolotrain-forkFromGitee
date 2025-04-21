# Docker部署指南

本文档提供使用Docker部署YOLOv8训练平台的详细步骤。

## 系统要求

- Docker 19.03+
- Docker Compose 1.27+
- 如果需要GPU支持，需要安装NVIDIA Container Toolkit

## 部署步骤

### 1. 安装Docker和Docker Compose

#### Ubuntu/Debian

```bash
# 安装Docker
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 将当前用户添加到docker组（可选，避免使用sudo）
sudo usermod -aG docker $USER
newgrp docker
```

#### Windows/macOS

下载并安装Docker Desktop：
- Windows: https://docs.docker.com/desktop/install/windows-install/
- macOS: https://docs.docker.com/desktop/install/mac-install/

### 2. 克隆代码仓库

```bash
git clone https://gitee.com/rock_kim/Myolotrain/
cd Myolotrain
```

### 3. 配置环境变量（可选）

如果需要自定义配置，可以创建`.env`文件：

```bash
# 创建.env文件
cat > .env << EOF
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=yolov8_platform
POSTGRES_SERVER=db
EOF
```

### 4. 使用CPU版本部署

```bash
# 构建并启动容器
docker-compose up -d

# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 5. 使用GPU版本部署

#### 安装NVIDIA Container Toolkit

```bash
# 添加NVIDIA软件包仓库
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# 安装NVIDIA Container Toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# 重启Docker服务
sudo systemctl restart docker
```

#### 部署GPU版本

```bash
# 构建并启动GPU版本容器
docker-compose -f docker-compose-gpu.yml up -d

# 查看容器状态
docker-compose -f docker-compose-gpu.yml ps

# 查看日志
docker-compose -f docker-compose-gpu.yml logs -f
```

### 6. 初始化数据库

```bash
# 进入容器
docker-compose exec web bash

# 初始化数据库
python init_db.py

# 退出容器
exit
```

## 访问应用

应用将在以下URL可用：

- Web界面: http://localhost:8000
- TensorBoard: http://localhost:6006

## 数据持久化

Docker Compose配置中已经设置了数据持久化：

- PostgreSQL数据存储在名为`postgres_data`的Docker卷中
- 应用的静态文件（上传、数据集、模型、结果）挂载到主机的`app/static`目录
- 日志文件挂载到主机的`logs`目录

## 更新应用

```bash
# 拉取最新代码
git pull

# 重新构建并启动容器
docker-compose down
docker-compose up -d --build

# 如果使用GPU版本
docker-compose -f docker-compose-gpu.yml down
docker-compose -f docker-compose-gpu.yml up -d --build
```

## 常见问题

### 1. 数据库连接错误

检查Docker Compose配置中的数据库连接信息是否正确，特别是用户名、密码和主机名。

```bash
# 检查数据库容器是否正常运行
docker-compose ps db

# 检查数据库日志
docker-compose logs db
```

### 2. GPU不可用

如果使用GPU版本但无法使用GPU，请检查NVIDIA Container Toolkit是否正确安装：

```bash
# 检查NVIDIA驱动是否正常
nvidia-smi

# 检查Docker中的GPU是否可用
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu20.04 nvidia-smi
```

### 3. 容器内存不足

如果容器内存不足，可以在Docker Compose配置中增加内存限制：

```yaml
services:
  web:
    # ... 其他配置 ...
    deploy:
      resources:
        limits:
          memory: 8G
```

### 4. 端口冲突

如果端口8000或6006已被占用，可以修改Docker Compose配置中的端口映射：

```yaml
services:
  web:
    # ... 其他配置 ...
    ports:
      - "8080:8000"  # 将主机的8080端口映射到容器的8000端口
      - "6007:6006"  # 将主机的6007端口映射到容器的6006端口
```

## 生产环境部署

对于生产环境，建议添加Nginx反向代理和HTTPS支持：

### 1. 创建Nginx配置

```bash
# 创建Nginx配置文件
cat > nginx.conf << EOF
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /tensorboard/ {
        proxy_pass http://web:6006/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
```

### 2. 添加Nginx服务到Docker Compose

```yaml
services:
  # ... 其他服务 ...
  
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web
    restart: always
```

### 3. 添加HTTPS支持（使用Certbot）

```bash
# 安装Certbot
sudo apt install -y certbot

# 获取SSL证书
sudo certbot certonly --standalone -d your_domain.com

# 复制证书到项目目录
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/your_domain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/your_domain.com/privkey.pem ssl/

# 更新Nginx配置
cat > nginx.conf << EOF
server {
    listen 80;
    server_name your_domain.com;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name your_domain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /tensorboard/ {
        proxy_pass http://web:6006/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# 重启Nginx容器
docker-compose restart nginx
```
