#!/bin/sh
# 容器启动入口：准备数据卷 → 等待数据库 → 初始化表结构 → 启动应用（CMD）
set -e

DATA_DIR="${DATA_DIR:-/data}"
APP_DIR=/app

# ---------------------------------------------------------------------
# 1. 把旧代码里写死的运行数据目录（app/static/<名称>、logs/、datasets_import/ 等）
#    软链到数据卷。这样旧代码不用改路径，数据也不会随容器重建而丢失。
#    新增数据目录时要同时加到这里和 .dockerignore。
# ---------------------------------------------------------------------
STATIC_DATA_DIRS="uploads datasets models results temp annotations extracted_frames batch_tasks \
mosaic_candidates augmented_datasets advanced_augmentations processed_images processed_videos \
video_datasets video_frames"

link_dir() {
  # link_dir <容器内路径> <数据卷内路径>
  target="$1"; store="$2"
  mkdir -p "$store"
  if [ -L "$target" ]; then
    return 0
  fi
  if [ -d "$target" ]; then
    # 镜像里已有同名目录（正常情况下为空）：先把内容合并进数据卷，不覆盖已有文件
    cp -an "$target/." "$store/" 2>/dev/null || true
    rm -rf "$target"
  fi
  mkdir -p "$(dirname "$target")"
  ln -s "$store" "$target"
}

for d in $STATIC_DATA_DIRS; do
  link_dir "$APP_DIR/app/static/$d" "$DATA_DIR/static/$d"
done
link_dir "$APP_DIR/logs" "$DATA_DIR/logs"
link_dir "$APP_DIR/datasets_import" "$DATA_DIR/datasets_import"
mkdir -p "$DATA_DIR/runs" "$DATA_DIR/uploads" "$DATA_DIR/config" "$DATA_DIR/logs/tensorboard"

# SAM 配置写在工作目录下的 sam3_config.json，同样指向数据卷（文件不存在时由应用首次保存时创建）
if [ ! -L "$APP_DIR/sam3_config.json" ]; then
  if [ -f "$APP_DIR/sam3_config.json" ] && [ ! -f "$DATA_DIR/config/sam3_config.json" ]; then
    cp "$APP_DIR/sam3_config.json" "$DATA_DIR/config/sam3_config.json"
  fi
  rm -f "$APP_DIR/sam3_config.json"
  ln -s "$DATA_DIR/config/sam3_config.json" "$APP_DIR/sam3_config.json"
fi

# Ultralytics 画图需要的字体：放进它的配置目录，避免运行时联网下载
if [ -n "$YOLO_CONFIG_DIR" ]; then
  mkdir -p "$YOLO_CONFIG_DIR"
  if [ ! -f "$YOLO_CONFIG_DIR/Arial.Unicode.ttf" ] && [ -f "$APP_DIR/app/static/fonts/Arial.Unicode.ttf" ]; then
    cp "$APP_DIR/app/static/fonts/Arial.Unicode.ttf" "$YOLO_CONFIG_DIR/"
  fi
fi

# ---------------------------------------------------------------------
# 2. 等待数据库并初始化表结构（建表、补字段、首次创建 admin）
# ---------------------------------------------------------------------
cd "$APP_DIR"
python -m app.db.wait_for_db
python -c "from app.db.init_db import init_db; init_db()"

# ---------------------------------------------------------------------
# 3. 启动应用
# ---------------------------------------------------------------------
exec "$@"
