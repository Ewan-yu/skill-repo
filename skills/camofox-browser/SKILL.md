---
name: camofox-browser
description: >
  基于 Camoufox 反指纹浏览器（C++ 级别指纹伪装）的通用浏览器自动化技能。
  专为需要绕过反爬检测、保持登录状态、模拟真实用户行为的场景设计。
  当用户需要以下任何操作时必须使用此技能：打开网站并抓取内容、处理登录流程
  （扫码登录、手机号登录、验证码、OAuth）、保存/恢复浏览器登录状态、
  填写表单、点击按钮、抓取页面数据、绕过反爬检测。
  即使用户没有明确说"用浏览器"，只要任务本质上需要操控网页（如"帮我打开XX网站"、
  "登录XX"、"把这个网页的内容保存下来"、"在网站上搜索XX"），都应使用此技能。
  也适用于 wxcj（微信公众号采集）等需要底层浏览器引擎的场景。
---

# camofox-browser 通用浏览器自动化

基于 [Camoufox](https://camoufox.com/) 反指纹浏览器引擎，C++ 级别的浏览器指纹伪装。

## 前置条件

- Git、Node.js 18+
- Windows 用 `python`，Linux/Mac 用 `python3`（下文统一写 `python`）
- 首次运行时 adapter 会自动从 GitHub 克隆并安装

## 文件结构

```
camofox-browser/
├── SKILL.md
├── scripts/
│   ├── camofox_adapter.py    # 核心适配器
│   └── auth_state.py         # 登录状态保存/恢复
└── references/
    ├── login-flows.md        # 登录流程详解（含 snapshot 格式说明、反爬处理）
    ├── auth-state.md         # 状态管理机制
    └── troubleshooting.md    # 常见问题
```

## 核心工具

所有命令通过 `python scripts/camofox_adapter.py` 调用：

| 命令 | 用途 |
|------|------|
| `init` | 初始化（自动安装+启动） |
| `open <URL>` | 新建 tab 并打开网页 |
| `navigate <TAB_ID> <URL>` | 在已有 tab 内跳转到新 URL |
| `screenshot <TAB_ID>` | 截图（`--view` 打开查看器） |
| `click <TAB_ID>` | 点击元素（`-s` CSS选择器 或 `--text` 文本） |
| `type <TAB_ID>` | 输入文本（`-s` 选择器 `-v` 内容） |
| `wait <TAB_ID>` | 等待条件（`-s` 元素出现 或 `-u` URL 正则） |
| `scroll <TAB_ID>` | 滚动页面（默认随机人类行为） |
| `eval <TAB_ID> <JS>` | 执行 JS（支持文件路径或内联表达式） |
| `snapshot <TAB_ID>` | 无障碍快照（检测页面结构，不截图） |
| `images <TAB_ID>` | 列出图片 |
| `links <TAB_ID>` | 列出链接 |
| `close <TAB_ID>` | 关闭 tab |
| `close-all` | 关闭所有 tab |
| `health` | 健康检查 |

全局参数：`--user-id USER`（默认 `camofox`，用于会话隔离）

---

## 用户体验原则

**截图只在用户必须亲眼看到内容时才用**，其他情况一律用 `snapshot`/`eval` 检测页面状态。截图会弹出查看器打扰用户，应当克制使用。

需要截图的场景（仅此几种）：
- 二维码扫码（用户必须看到图片才能操作）
- 滑块/图形验证码（用户需要手动处理）
- 登录失败时展示错误（帮助用户理解问题）

**不需要截图的场景**（用 `snapshot`/`eval` 代替）：
- 普通网页打开、内容浏览 → 用 `snapshot` 或 `eval` 读取内容
- 页面加载确认 → 用 `wait -s "body"`
- 登录状态检测 → 用 `auth_state.py check`
- 弹窗处理确认 → 用 `snapshot` 检查弹窗是否消失

**需要用户介入时，立即告知并等待**，不要静默跳过或假装成功：

| 场景 | 处理方式 |
|------|----------|
| 二维码扫码 | 截图 `--view` 展示，明确告知用户扫码，等待用户确认 |
| 手机验证码 | 告知用户查看手机，等待用户提供验证码后再继续 |
| 滑块/图形验证码 | 截图展示，告知用户手动处理，等待用户确认完成 |
| 登录失败 | 截图展示错误，说明原因，询问用户如何继续 |

**能自动处理的不打扰用户**：
- 同意弹窗、Cookie 确认 → 自动点击
- 页面加载等待 → 用 `wait` 命令，不用 `sleep`
- 登录状态检测 → 用 `snapshot`/`eval`，不截图

---

## 工作流：打开并浏览网页

打开网页后用 `snapshot` 或 `eval` 读取内容，不需要截图。截图会弹出查看器打扰用户，普通浏览场景不应使用。

```bash
# 初始化
python scripts/camofox_adapter.py init

# 打开网页
TAB_ID=$(python scripts/camofox_adapter.py open "https://example.com")

# 等待加载（用 wait 而非 sleep）
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

# 读取页面内容（用 snapshot 或 eval，不截图）
python scripts/camofox_adapter.py snapshot $TAB_ID
```

**页面加载后，主动向用户汇报页面情况**，因为用户看不到浏览器窗口，需要你来充当他们的"眼睛"。汇报内容包括：

- 页面是什么（标题、类型：新闻首页 / 登录页 / 文章详情 / 搜索结果…）
- 页面上有哪些主要功能或内容区块（导航栏、搜索框、文章列表、登录入口…）
- 如果需要登录才能继续，告知用户并询问是否登录
- 根据页面内容，给出 2-3 个用户可能想做的下一步操作建议

**示例汇报格式**（根据实际内容灵活调整，不要照搬）：

> 页面已打开，这是网易新闻首页。页面上有：顶部导航（新闻、娱乐、体育、科技等频道）、搜索框、今日头条新闻列表。
>
> 你可以：
> - 告诉我你想看哪个频道的内容
> - 搜索某个关键词
> - 让我提取当前首页的新闻标题列表

---

## 工作流：处理登录

登录流程的完整细节见 `references/login-flows.md`，这里是骨架：

### Step 1：打开登录页，处理弹窗（自动）

```bash
TAB_ID=$(python scripts/camofox_adapter.py open "https://example.com/login")
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 15
```

用 snapshot 检查是否有弹窗（用户协议、Cookie 确认等），有则自动处理。**弹窗必须在截图前清除，否则会遮挡二维码**：

```bash
SNAP=$(python scripts/camofox_adapter.py snapshot $TAB_ID)
# 如果 snapshot 中出现"同意/接受/确定"等按钮，逐一点击
for btn in "同意" "接受" "Accept" "Agree" "确定" "OK"; do
    python scripts/camofox_adapter.py click $TAB_ID --text "$btn" 2>/dev/null && sleep 1
done
```

### Step 2：识别登录类型，按需处理

弹窗处理完后，再次 snapshot 判断登录类型：

```bash
SNAP=$(python scripts/camofox_adapter.py snapshot $TAB_ID)
# - 含 "二维码/qr/扫码" 或有 iframe → 二维码登录
# - 含 "input [type=password]" → 表单登录
# - 含 "滑块/验证码/captcha" → 反爬校验
```

**二维码登录**（需用户介入）：

二维码通常在 iframe 内，snapshot 无法读取图片内容，必须截图展示。截图前确认弹窗已清除：

```bash
# 如有"获取二维码"之类的按钮，先点击触发
python scripts/camofox_adapter.py click $TAB_ID --text "获取登录二维码" 2>/dev/null
sleep 1

# 截图并弹出查看器让用户扫码
python scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/qr.png --view
# 告知用户："请用微信/App 扫描截图中的二维码，扫码完成后告诉我"
# ← 等待用户确认
```

**表单登录**（自动）：
```bash
python scripts/camofox_adapter.py type $TAB_ID -s "input[type=email], input[name=username]" -v "user@example.com"
python scripts/camofox_adapter.py type $TAB_ID -s "input[type=password]" -v "secret"
python scripts/camofox_adapter.py click $TAB_ID -s "button[type=submit]"
```

**反爬校验**（需用户介入）：
```bash
python scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/captcha.png --view
# 告知用户："页面出现了验证码，需要你手动处理，完成后告诉我"
# ← 等待用户确认
```

### Step 3：检测登录成功（正向检测）

用 eval 检查 URL 是否已离开登录页，或等待登录后才出现的元素：

```bash
# 方式一：等待 URL 变化（记录初始 URL，检测是否跳转）
INITIAL_URL=$(python scripts/camofox_adapter.py eval $TAB_ID "location.href")
# 用户操作后检测：
CURRENT_URL=$(python scripts/camofox_adapter.py eval $TAB_ID "location.href")
# 如果 URL 变化且 snapshot 不再含登录相关内容，则登录成功

# 方式二：等待已知的成功路径
python scripts/camofox_adapter.py wait $TAB_ID --url-pattern "/group/|/home|/dashboard|/feed" --timeout 120
```

### Step 4：保存登录状态（自动执行，无需询问）

登录成功后直接保存，不要问用户是否需要——这是默认应该做的事。

```bash
mkdir -p auth_states
python scripts/auth_state.py save $TAB_ID --output auth_states/example_com.json
# 告知用户保存位置，方便下次使用
```

---

## 工作流：恢复登录状态

```bash
# 打开目标页面
TAB_ID=$(python scripts/camofox_adapter.py open "https://example.com")
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 10

# 注入登录状态
python scripts/auth_state.py restore $TAB_ID --input auth_states/example_com.json

# 刷新页面让状态生效（navigate 比 close+open 更简洁）
python scripts/camofox_adapter.py navigate $TAB_ID "https://example.com/dashboard"
python scripts/camofox_adapter.py wait $TAB_ID -s "body" --timeout 10

# 验证登录状态
python scripts/auth_state.py check $TAB_ID
```

---

## 工作流：内容提取

```bash
# 获取页面文本
python scripts/camofox_adapter.py eval $TAB_ID "document.body.innerText.substring(0, 5000)"

# 获取结构化快照
python scripts/camofox_adapter.py snapshot $TAB_ID

# 获取所有链接
python scripts/camofox_adapter.py links $TAB_ID

# 获取所有图片
python scripts/camofox_adapter.py images $TAB_ID
```

---

## 登录状态管理

```bash
# 保存
python scripts/auth_state.py save $TAB_ID --output auth_states/mysite.json

# 恢复
python scripts/auth_state.py restore $TAB_ID -i auth_states/mysite.json

# 检查（返回 cookies 数量、localStorage 数量、当前 URL）
python scripts/auth_state.py check $TAB_ID
```

**已知限制**：`httpOnly` cookies 无法通过 JS 读取，详见 `references/auth-state.md`。

---

## 故障排除

详见 `references/troubleshooting.md`。常见问题：

- camofox-browser 无法启动 → 检查 Node.js 版本（需 18+）、端口占用（9377）
- 截图空白 → 页面未加载完成，用 `wait -s "body"` 替代 `sleep`
- 登录状态恢复失败 → token 可能已过期，需重新登录
- 元素点击不生效 → 先用 `snapshot` 确认元素存在，检查是否被遮挡
- 反复触发反爬 → 增加操作间隔，或先在真实浏览器登录后保存状态
