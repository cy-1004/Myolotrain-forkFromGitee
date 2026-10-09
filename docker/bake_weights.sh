#!/bin/sh
# 构建镜像时预置权重：bake_weights.sh <目标目录> <权重文件名...>
# 优先使用构建上下文 docker/weights/ 下的同名文件（构建机无法访问 GitHub 时用），没有才下载。
set -e
dest="$1"; shift
mkdir -p "$dest"
for w in "$@"; do
  if [ -f "/tmp/weights/$w" ]; then
    echo "使用本地权重 $w"
    cp "/tmp/weights/$w" "$dest/"
  else
    echo "下载权重 $w"
    YOLO_CONFIG_DIR=/tmp/ultralytics python -c \
      "import sys; from ultralytics.utils.downloads import attempt_download_asset; attempt_download_asset(sys.argv[1])" \
      "$dest/$w"
  fi
  if [ ! -s "$dest/$w" ]; then
    echo "权重 $w 预置失败" >&2
    exit 1
  fi
done
rm -rf /tmp/ultralytics
