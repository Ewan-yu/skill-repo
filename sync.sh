#!/bin/bash
# sync.sh - 拉取最新技能并重新安装符号链接
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "拉取最新更改..."
cd "$REPO_DIR"
git pull --rebase

echo ""
echo "重新安装符号链接..."
bash ./install.sh

echo ""
echo "同步完成。"
