#!/bin/bash
# scripts/security-scan.sh
# 扫描仓库中的敏感信息

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "扫描仓库: $REPO_DIR"
echo ""

# 扫描 API 密钥
echo "1. 扫描 API 密钥..."
grep -r -l -E "(api_key|apikey|secret|token|password)\s*[:=]" "$REPO_DIR/skills/" 2>/dev/null | while read f; do
    echo "  ⚠️  $f"
done

# 扫描硬编码路径
echo ""
echo "2. 扫描硬编码路径..."
grep -r -l -E "[A-Z]:/[A-Za-z]" "$REPO_DIR/skills/" 2>/dev/null | while read f; do
    echo "  ⚠️  $f"
done

# 扫描可能的密钥值（32位以上字符串）
echo ""
echo "3. 扫描可能的密钥值..."
grep -r -E "['\"][a-zA-Z0-9_\-]{32,}['\"]" "$REPO_DIR/skills/" 2>/dev/null | head -10 | while read line; do
    echo "  ⚠️  $line"
done

echo ""
echo "扫描完成。"
