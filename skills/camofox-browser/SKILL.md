---
name: camofox-browser
description: >
  基于 Camoufox 反指纹浏览器（C++ 级别指纹伪装）的通用浏览器自动化技能。
  当用户需要以下任何操作时必须使用此技能：打开任意网站、浏览网页、网页截图、
  处理登录流程（扫码登录、手机号登录、验证码、OAuth）、保存/恢复浏览器登录状态、
  从网页提取内容（文章、图片、链接）、填写表单、点击按钮、抓取页面数据、
  模拟真实用户浏览行为、绕过反爬检测、或任何需要程序化浏览器交互的任务。
  即使用户没有明确说"用浏览器"，只要任务本质上需要操控网页（如"帮我打开XX网站"、
  "登录XX"、"把这个网页的内容保存下来"、"在网站上搜索XX"），都应使用此技能。
  也适用于 wxcj（微信公众号采集）等需要底层浏览器引擎的场景。
---

# camofox-browser 通用浏览器自动化

基于 [Camoufox](https://camoufox.com/) 反指纹浏览器引擎，提供 C++ 级别的浏览器指纹伪装能力。适用于需要绕过反爬检测、模拟真实用户浏览行为的场景。

## 截图原则

**只在需要用户肉眼查看时才截图。** 截图会产生临时文件，频繁截图浪费磁盘且对用户造成干扰。判断标准：

- **需要截图**：二维码扫码（用户必须看到图片才能操作）
- **不需要截图**：页面加载确认、登录状态检测、弹窗处理确认、表单填写结果 — 这些用 `snapshot`、`eval`、`auth_state.py check` 即可判断

## 前置条件

- Git、Node.js 18+
- 首次运行时 adapter 会自动从 GitHub 克隆并安装 camofox-browser

## 文件结构

```
camofox-browser/
├── SKILL.md
├── scripts/
│   ├── camofox_adapter.py    # 核心适配器（CLI + HTTP API 封装）
│   └── auth_state.py         # 登录状态保存/恢复
└── references/
    ├── login-flows.md        # 登录流程详解
    ├── auth-state.md         # 状态管理机制
    └── troubleshooting.md    # 常见问题
```

## 核心工具

所有命令通过 `python3 scripts/camofox_adapter.py` 调用：

| 命令 | 用途 | 示例 |
|------|------|------|
| `init` | 初始化（自动安装+启动） | `python3 scripts/camofox_adapter.py init` |
| `open <URL>` | 打开网页 | `python3 scripts/camofox_adapter.py open "https://example.com"` |
| `screenshot <TAB_ID>` | 截图保存（默认不弹查看器） | `python3 scripts/camofox_adapter.py screenshot $TAB_ID` |
| `click <TAB_ID>` | 点击元素 | `python3 scripts/camofox_adapter.py click $TAB_ID --text "登录"` |
| `type <TAB_ID>` | 输入文本 | `python3 scripts/camofox_adapter.py type $TAB_ID -s "input[name=q]" -v "搜索词"` |
| `wait <TAB_ID>` | 等待条件 | `python3 scripts/camofox_adapter.py wait $TAB_ID -s ".dashboard" --timeout 30` |
| `scroll <TAB_ID>` | 滚动页面 | `python3 scripts/camofox_adapter.py scroll $TAB_ID` |
| `eval <TAB_ID> <JS>` | 执行 JS | `python3 scripts/camofox_adapter.py eval $TAB_ID "document.title"` |
| `snapshot <TAB_ID>` | 无障碍快照 | `python3 scripts/camofox_adapter.py snapshot $TAB_ID` |
| `images <TAB_ID>` | 列出图片 | `python3 scripts/camofox_adapter.py images $TAB_ID` |
| `links <TAB_ID>` | 列出链接 | `python3 scripts/camofox_adapter.py links $TAB_ID` |
| `close <TAB_ID>` | 关闭标签 | `python3 scripts/camofox_adapter.py close $TAB_ID` |
| `close-all` | 关闭所有标签 | `python3 scripts/camofox_adapter.py close-all` |
| `health` | 健康检查 | `python3 scripts/camofox_adapter.py health` |

全局参数：`--user-id USER`（默认 `camofox`，用于会话隔离）

## 工作流：打开并浏览网页

**截图原则：只在需要用户肉眼查看时才截图（如二维码扫码）。其余场景用 `snapshot`/`eval` 检测页面状态即可，避免产生无用截图文件。**

```bash
# Step 1: 初始化
python3 scripts/camofox_adapter.py init

# Step 2: 打开网页
TAB_ID=$(python3 scripts/camofox_adapter.py open "https://example.com")

# Step 3: 等待加载，用 snapshot 确认页面就绪（不截图）
sleep 3
python3 scripts/camofox_adapter.py snapshot $TAB_ID

# Step 4: 滚动浏览（模拟人类）
python3 scripts/camofox_adapter.py scroll $TAB_ID

# Step 5: 完成后关闭
python3 scripts/camofox_adapter.py close $TAB_ID
```

## 工作流：处理登录（关键流程）

camofox-browser 是无头运行的，用户看不到浏览器窗口。登录流程需要截图桥接，但**只在必要时截图**（二维码展示），其余用 `snapshot`/`eval` 检测。

### Phase 1: 打开登录页并检测

```bash
TAB_ID=$(python3 scripts/camofox_adapter.py open "https://example.com/login")
sleep 3

# 用 snapshot 检测页面结构，判断登录类型（不截图）
python3 scripts/camofox_adapter.py snapshot $TAB_ID
```

通过 snapshot 分析登录类型：
- **同意弹窗**：有"同意"、"接受"等按钮 → 先处理（见 Phase 2a）
- **二维码登录**：页面有 QR 码图片
- **表单登录**：有用户名/密码输入框
- **OAuth 登录**：有第三方登录按钮

### Phase 2a: 处理同意弹窗（优先处理）

如果页面弹出隐私协议/用户协议确认框，**必须先处理**，否则会遮挡后续操作：

```bash
python3 scripts/camofox_adapter.py click $TAB_ID --text "同意"
sleep 2

# 用 snapshot 确认弹窗已关闭（不截图）
python3 scripts/camofox_adapter.py snapshot $TAB_ID
```

多层弹窗需循环处理，直到 snapshot 中不再出现弹窗相关内容。

### Phase 2b: 二维码登录

处理完所有弹窗后，二维码才会完整展示。**此时是唯一需要截图的场景** — 使用 `--view` 打开查看器让用户扫码：

```bash
python3 scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/qr.png --view
```

告知用户扫码，然后轮询等待登录成功（**不截图**，用 `eval` 检测 URL 变化）：

```bash
for i in $(seq 1 24); do
    sleep 5
    URL=$(python3 scripts/camofox_adapter.py eval $TAB_ID "location.href")
    # 如果 URL 不再是登录页，说明登录成功
    if echo "$URL" | grep -qv "login"; then
        echo "登录成功"
        break
    fi
    echo "等待扫码... ($i/24)"
done
```

**注意**：二维码通常 60-120 秒过期。如果过期，需要重新触发获取二维码。

### Phase 2c: 表单登录

```bash
# 填写用户名（兼容 React/Vue 框架）
python3 scripts/camofox_adapter.py type $TAB_ID -s "input[name=username]" -v "user@example.com"

# 填写密码
python3 scripts/camofox_adapter.py type $TAB_ID -s "input[name=password]" -v "secret123"

# 点击登录按钮
python3 scripts/camofox_adapter.py click $TAB_ID -s "button[type=submit]"

# 等待跳转，用 eval 确认登录成功（不截图）
sleep 3
python3 scripts/camofox_adapter.py eval $TAB_ID "location.href"
```

### Phase 3: 保存登录状态

登录成功后，保存认证状态以便后续使用：

```bash
python3 scripts/auth_state.py save $TAB_ID --output auth_states/example_com.json
python3 scripts/camofox_adapter.py close $TAB_ID
```

## 工作流：恢复登录状态

后续会话无需重新扫码，直接注入保存的状态：

```bash
# 打开目标页面
TAB_ID=$(python3 scripts/camofox_adapter.py open "https://example.com/dashboard")

# 注入登录状态
python3 scripts/auth_state.py restore $TAB_ID --input auth_states/example_com.json

# 关闭并重新打开（让状态生效）
python3 scripts/camofox_adapter.py close $TAB_ID
TAB_ID=$(python3 scripts/camofox_adapter.py open "https://example.com/dashboard")
sleep 2

# 验证登录状态（用 check 命令，不截图）
python3 scripts/auth_state.py check $TAB_ID
```

## 工作流：页面交互

### 点击元素

```bash
# 通过 CSS 选择器
python3 scripts/camofox_adapter.py click $TAB_ID -s "button.submit"

# 通过文本内容（自动查找包含该文本的元素）
python3 scripts/camofox_adapter.py click $TAB_ID --text "查看更多"
```

### 输入文本

```bash
# 自动兼容 React/Vue/Angular 框架的 input 事件
python3 scripts/camofox_adapter.py type $TAB_ID -s "#search-input" -v "搜索关键词"
```

### 等待条件

```bash
# 等待元素出现
python3 scripts/camofox_adapter.py wait $TAB_ID -s ".loaded-content" --timeout 30

# 等待 URL 变化
python3 scripts/camofox_adapter.py wait $TAB_ID -u "/dashboard" --timeout 15
```

### 执行自定义 JS

```bash
# 内联表达式
python3 scripts/camofox_adapter.py eval $TAB_ID "document.querySelectorAll('a').length"

# 通过文件
python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_page_info.js
```

## 工作流：内容提取

```bash
# 获取页面文本摘要
python3 scripts/camofox_adapter.py eval $TAB_ID "document.body.innerText.substring(0, 3000)"

# 获取所有链接
python3 scripts/camofox_adapter.py links $TAB_ID

# 获取所有图片
python3 scripts/camofox_adapter.py images $TAB_ID

# 获取无障碍快照（结构化页面内容）
python3 scripts/camofox_adapter.py snapshot $TAB_ID
```

## 登录状态管理

状态文件保存 cookies 和 localStorage 到 JSON：

```json
{
  "saved_at": "2026-05-10T14:30:00+00:00",
  "url": "https://example.com/dashboard",
  "domain": "example.com",
  "cookies": {"session": "abc123"},
  "localStorage": {"user_id": "12345", "token": "bearer xxx"}
}
```

**管理命令：**

```bash
# 保存
python3 scripts/auth_state.py save $TAB_ID --output auth_states/mysite.json

# 恢复
python3 scripts/auth_state.py restore $TAB_ID -i auth_states/mysite.json

# 检查登录状态
python3 scripts/auth_state.py check $TAB_ID
```

**已知限制：** `document.cookie` 无法读取 httpOnly cookies。详见 `references/auth-state.md`。

## Windows 编码说明

所有脚本已内置 Windows UTF-8 输出处理（`PYTHONUTF8=1`、`reconfigure`）。如遇编码问题，确保系统支持 UTF-8。

## 故障排除

详见 `references/troubleshooting.md`。常见问题：

- camofox-browser 无法启动 → 检查 Node.js 版本、端口占用
- 截图空白 → 页面未加载完成，增加等待时间
- 登录状态恢复失败 → token 可能已过期，需重新登录
- JS eval 报错 → 检查选择器是否正确、页面是否已加载
