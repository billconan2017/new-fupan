#!/bin/bash
set -e
# 构建前端并把产物拷贝到后端服务可托管的 dist/
cd "$(dirname "$0")/frontend"

echo "=== Building FuPanX Frontend ==="
npm run build

echo "=== Copying dist ==="
cp -r dist/* ../dist/

echo "=== Done ==="
echo "Access at http://your-ip:9009/"
