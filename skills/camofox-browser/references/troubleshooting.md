# 故障排除

## camofox-browser 无法启动

### 端口被占用

```
Error: Cannot reach camofox-browser at http://127.0.0.1:9377
```

**解决**：
```bash
# 查找占用端口的进程（Windows）
netstat -ano | findstr :9377
# 杀掉进程
taskkill /PID <进程号> /F
```

### Node.js 版本问题

camofox-browser 需要 Node.js 18+。

```bash
node --version  # 确认版本 >= 18
```

### npm install 失败

```bash
# 清除缓存重试
cd ~/.hermes/camofox-browser
rm -rf node_modules
npm install
```

### Git 克隆失败

检查网络连接和 Git 配置：

```bash
git clone --depth 1 https://github.com/jo-inc/camofox-browser.git ~/.hermes/camofox-browser
```

## 截图问题

### 截图空白

**原因**：页面未加载完成就截图。

**解决**：增加等待时间，或使用 `wait` 命令：

```bash
TAB_ID=$(python3 scripts/camofox_adapter.py open "https://example.com")
sleep 5  # 增加等待
python3 scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/page.png

# 或者等待特定元素出现
python3 scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 10
python3 scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/page.png
```

### 截图打不开

**原因**：文件路径包含特殊字符或中文。

**解决**：使用纯英文路径：

```bash
python3 scripts/camofox_adapter.py screenshot $TAB_ID --output C:/temp/screenshot.png
```

## JS Eval 错误

### 元素未找到

```
Element not found: .some-selector
```

**解决**：
1. 先用 `snapshot` 确认页面结构
2. 检查选择器是否正确
3. 确认页面已加载完成

### 权限被拒绝

某些页面的 CSP（Content Security Policy）可能阻止内联脚本执行。

**解决**：使用外部 JS 文件：

```bash
# 将 JS 写入文件
echo "document.title" > /tmp/script.js
python3 scripts/camofox_adapter.py eval $TAB_ID /tmp/script.js
```

## 登录状态问题

### 恢复后仍需登录

**可能原因**：
1. Token 已过期（通常几小时到几天）
2. httpOnly cookie 无法保存（见 `auth-state.md`）
3. 网站使用了设备指纹绑定

**解决**：重新执行登录流程并保存新的状态。

### localStorage 恢复后不生效

**原因**：某些 SPA 应用在加载时读取 localStorage，之后不会重新读取。

**解决**：恢复状态后需要刷新页面或重新打开：

```bash
python3 scripts/auth_state.py restore $TAB_ID -i auth.json
python3 scripts/camofox_adapter.py close $TAB_ID
TAB_ID=$(python3 scripts/camofox_adapter.py open "https://example.com")
```

## 中文编码问题（Windows）

### 现象

输出中文时出现乱码或报错 `UnicodeEncodeError: 'gbk' codec can't encode character`。

**解决**：所有脚本已内置 Windows UTF-8 处理。如果仍有问题：

```bash
# 设置环境变量
set PYTHONUTF8=1
# 或在 PowerShell 中
$env:PYTHONUTF8 = "1"
```

## 元素点击不生效

### 原因

1. 元素被其他元素遮挡
2. 元素在视口外
3. 元素是动态生成的（需要等待）

### 解决

adapter 的 `click` 命令已内置 `scrollIntoView`。如果仍不生效：

```bash
# 先滚动到元素位置
python3 scripts/camofox_adapter.py eval $TAB_ID '
  document.querySelector(".target").scrollIntoView({block: "center"})
'
sleep 1
# 再点击
python3 scripts/camofox_adapter.py click $TAB_ID -s ".target"
```

### Shadow DOM 元素

如果元素在 Shadow DOM 内，常规选择器无法访问。需要通过 JS 穿透：

```bash
python3 scripts/camofox_adapter.py eval $TAB_ID '
  document.querySelector("host-element").shadowRoot.querySelector(".target").click()
'
```

## Tab 管理

### 查看当前活跃的 tab

```bash
python3 scripts/camofox_adapter.py health
```

health 输出中的 `activeTabs` 字段显示当前活跃标签数。

### 清理所有 tab

```bash
python3 scripts/camofox_adapter.py close-all
```

### Tab 操作超时

HTTP 请求默认超时 120 秒。对于慢速网站，可在 adapter 代码中调整 `timeout` 参数，或增加 `wait` 命令的等待时间：

```bash
# 先等待页面加载完成
python3 scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 60
python3 scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/page.png
```
