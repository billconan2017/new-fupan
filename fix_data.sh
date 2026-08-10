#!/bin/bash
# 重新拉取全部数据（修复字段映射后使用）。
# 用法：先确保后端已在 127.0.0.1:9009 运行，并按需激活虚拟环境。
set -e
cd "$(dirname "$0")/backend"
BASE="http://127.0.0.1:9009"

echo "=== Re-fetching all data with fixed field mappings ==="

echo "1. Pools..."
curl -s --max-time 20 -X POST "$BASE/api/pools/fetch/limit_up"; echo
curl -s --max-time 20 -X POST "$BASE/api/pools/fetch/limit_down"; echo
curl -s --max-time 20 -X POST "$BASE/api/pools/fetch/broken_board"; echo
curl -s --max-time 20 -X POST "$BASE/api/pools/fetch/strong"; echo

echo "2. Dragon tiger..."
curl -s --max-time 20 -X POST "$BASE/api/dragon/fetch/tiger"; echo

echo "3. Emotion..."
curl -s --max-time 20 -X POST "$BASE/api/emotion/fetch"; echo

echo "4. Capital flow..."
curl -s --max-time 30 -X POST "$BASE/api/capital/fetch"; echo

echo "5. Review report..."
curl -s --max-time 15 -X POST "$BASE/api/review/generate"; echo

echo "=== Done ==="
