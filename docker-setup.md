# Docker 配置说明

为了解决 Docker Hub 连接超时问题，我们已经进行了以下优化：

## 已完成的优化

1. **修改了 docker-compose.yml**：
   - 移除了过时的 version 字段
   - 使用阿里云镜像源替代官方镜像源
   - 添加了容器名称
   - 添加了健康检查
   - 优化了依赖关系

2. **修改了 Dockerfile**：
   - 使用阿里云镜像源替代官方镜像源
   - 配置了 apt 使用中科大镜像源
   - 配置了 pip 使用清华大学镜像源

3. **创建了 .env 文件**：
   - 提供了代理设置选项
   - 设置了镜像仓库和数据库参数

4. **创建了 .dockerignore 文件**：
   - 排除不必要的文件，加快构建速度

## 使用方法

### 1. 配置 Docker 守护进程（一次性操作）

将 `daemon.json` 文件复制到 Docker 的配置目录：

```
# Windows
copy daemon.json %USERPROFILE%\.docker\daemon.json

# 或手动复制到 C:\Users\<用户名>\.docker\daemon.json
```

然后重启 Docker Desktop。

### 2. 直接使用 docker-compose 启动

```
docker-compose up -d
```

### 3. 如果仍然遇到问题

如果仍然遇到连接超时问题，可以尝试手动拉取镜像：

```
docker pull registry.cn-hangzhou.aliyuncs.com/library/postgres:13
docker pull registry.cn-hangzhou.aliyuncs.com/library/python:3.9-slim
```

然后再次运行：

```
docker-compose up -d
```

## 故障排除

如果遇到以下错误：

- **context deadline exceeded**：这通常是网络连接问题，请检查您的网络连接或使用代理。
- **repository does not exist**：请确认镜像名称是否正确，或者尝试使用其他镜像源。
- **authentication required**：某些镜像源可能需要认证，请检查镜像源设置。

## 其他有用的命令

- 查看容器状态：`docker-compose ps`
- 查看容器日志：`docker-compose logs -f`
- 停止所有容器：`docker-compose down`
- 重建并启动容器：`docker-compose up -d --build`
