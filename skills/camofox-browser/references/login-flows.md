# 登录流程详解

本文档描述 camofox-browser 处理各种登录场景的标准流程。

## 目录

1. [snapshot 输出格式](#snapshot-输出格式)
2. [通用前置：处理同意弹窗](#通用前置处理同意弹窗)
3. [二维码登录](#二维码登录)
4. [表单登录](#表单登录)
5. [多步骤登录（手机验证码）](#多步骤登录手机验证码)
6. [OAuth/SSO 登录](#oauthsso-登录)
7. [反爬校验处理](#反爬校验处理)
8. [登录成功判断](#登录成功判断)

---

## snapshot 输出格式

`snapshot` 返回页面的无障碍树文本，格式类似：

```
document
  heading "登录" [level=1]
  img "二维码" [src=data:image/png;base64,...]
  button "刷新二维码"
  text "请使用微信扫描二维码登录"
  link "手机号登录"
```

用途：
- 判断页面类型（有 `img "二维码"` → 二维码登录；有 `input [type=password]` → 表单登录）
- 检测弹窗（有 `dialog` 或 `button "同意"` → 需要处理弹窗）
- 检测反爬（有 `"验证"、"滑块"、"人机"` 等关键词 → 需要用户介入）
- 确认操作结果（点击后 snapshot 不再包含弹窗 → 弹窗已关闭）

---

## 通用前置：处理同意弹窗

**打开任何登录页后，第一步都是检测并清除弹窗**，否则弹窗会遮挡二维码或表单。

```bash
TAB_ID=$(python camofox_adapter.py open "https://example.com/login")
python camofox_adapter.py wait $TAB_ID -s "body" --timeout 15

# 检测弹窗
SNAP=$(python camofox_adapter.py snapshot $TAB_ID)
echo "$SNAP" | grep -i "同意\|接受\|agree\|accept\|cookie"
```

如果有弹窗，循环处理直到干净：

```bash
for btn in "同意" "接受" "Accept" "Agree" "确定" "OK"; do
    python camofox_adapter.py click $TAB_ID --text "$btn" 2>/dev/null && sleep 1
done

# 确认弹窗已消失
python camofox_adapter.py snapshot $TAB_ID
```

---

## 二维码登录

### 检测

```bash
SNAP=$(python camofox_adapter.py snapshot $TAB_ID)
echo "$SNAP" | grep -i "二维码\|qr\|扫码\|扫描"
```

### 标准流程

```bash
# 1. 处理完所有弹窗后，截图展示二维码给用户（唯一需要截图的场景）
python camofox_adapter.py screenshot $TAB_ID --output /tmp/qr.png --view
echo "请扫描截图中的二维码，扫码后告诉我"

# 2. 等待用户扫码（用户确认后再继续）
# 用户扫码完成后，检测登录成功
```

### 登录成功检测

不要用 URL 是否包含 "login" 来判断，应该正向检测成功状态：

```bash
# 方式一：等待跳转到已知的成功路径
python camofox_adapter.py wait $TAB_ID --url-pattern "/dashboard|/home|/feed|/index" --timeout 120

# 方式二：等待登录后才出现的元素
python camofox_adapter.py wait $TAB_ID -s ".user-avatar, .logout-btn, [data-user]" --timeout 120

# 方式三：轮询检测（适合不确定成功路径的情况）
INITIAL_URL=$(python camofox_adapter.py eval $TAB_ID "location.href")
for i in $(seq 1 24); do
    sleep 5
    CURRENT_URL=$(python camofox_adapter.py eval $TAB_ID "location.href")
    if [ "$CURRENT_URL" != "$INITIAL_URL" ]; then
        echo "URL 已变化，登录可能成功: $CURRENT_URL"
        # 进一步确认：检查是否还在登录相关页面
        SNAP=$(python camofox_adapter.py snapshot $TAB_ID)
        if ! echo "$SNAP" | grep -qi "登录\|login\|sign.in\|二维码"; then
            echo "登录成功"
            break
        fi
    fi
    echo "等待扫码... ($i/24)"
done
```

### 二维码过期处理

```bash
# 检测过期
SNAP=$(python camofox_adapter.py snapshot $TAB_ID)
if echo "$SNAP" | grep -qi "过期\|失效\|刷新\|expire\|refresh"; then
    python camofox_adapter.py click $TAB_ID --text "刷新" 2>/dev/null || \
    python camofox_adapter.py click $TAB_ID --text "点击刷新" 2>/dev/null
    sleep 2
    python camofox_adapter.py screenshot $TAB_ID --output /tmp/qr_new.png --view
    echo "二维码已刷新，请重新扫码"
fi
```

---

## 表单登录

### 检测

```bash
SNAP=$(python camofox_adapter.py snapshot $TAB_ID)
echo "$SNAP" | grep -i "input.*password\|密码\|password"
```

### 标准流程

```bash
# 填写用户名
python camofox_adapter.py type $TAB_ID -s "input[name=username], input[name=email], input[type=email]" -v "user@example.com"

# 填写密码
python camofox_adapter.py type $TAB_ID -s "input[name=password], input[type=password]" -v "secret"

# 提交
python camofox_adapter.py click $TAB_ID -s "button[type=submit]" 2>/dev/null || \
python camofox_adapter.py click $TAB_ID --text "登录"

# 等待登录成功（见"登录成功检测"）
python camofox_adapter.py wait $TAB_ID --url-pattern "/dashboard|/home|/feed" --timeout 15
```

### React/Vue 框架兼容

adapter 的 `type` 命令已内置框架兼容处理（通过 native setter + input/change 事件）。如果某个特殊框架仍不响应，用逐字符模拟：

```bash
python camofox_adapter.py eval $TAB_ID '
  (() => {
    const el = document.querySelector("input[name=q]");
    el.focus();
    el.value = "";
    for (const char of "搜索词") {
      el.value += char;
      el.dispatchEvent(new KeyboardEvent("keydown", {key: char, bubbles: true}));
      el.dispatchEvent(new InputEvent("input", {data: char, inputType: "insertText", bubbles: true}));
      el.dispatchEvent(new KeyboardEvent("keyup", {key: char, bubbles: true}));
    }
    el.dispatchEvent(new Event("change", {bubbles: true}));
  })()
'
```

---

## 多步骤登录（手机验证码）

```bash
# Step 1: 输入手机号
python camofox_adapter.py type $TAB_ID -s "input[name=phone], input[type=tel]" -v "13800138000"
python camofox_adapter.py click $TAB_ID --text "获取验证码"
sleep 2

# Step 2: 告知用户，等待用户提供验证码
echo "验证码已发送到手机，请告诉我收到的验证码"
# ← 此处等待用户回复

# Step 3: 用户提供验证码后输入（将 123456 替换为用户提供的值）
python camofox_adapter.py type $TAB_ID -s "input[name=code], input[name=sms_code]" -v "123456"
python camofox_adapter.py click $TAB_ID -s "button[type=submit]"
```

---

## OAuth/SSO 登录

OAuth 登录通常会打开新窗口或重定向。camofox-browser 的 tab 会跟随重定向，但弹出窗口需要特殊处理。

**推荐**：如果用户有账号密码，优先使用表单登录而非 OAuth，避免弹窗问题。

如果必须用 OAuth：

```bash
# 点击第三方登录按钮
python camofox_adapter.py click $TAB_ID --text "使用微信登录" 2>/dev/null || \
python camofox_adapter.py click $TAB_ID --text "Google"

# 等待重定向完成
sleep 3
python camofox_adapter.py snapshot $TAB_ID
```

---

## 反爬校验处理

反爬校验（滑块、图形验证码、人机验证）**无法自动处理**，必须告知用户介入。

### 检测

```bash
SNAP=$(python camofox_adapter.py snapshot $TAB_ID)
if echo "$SNAP" | grep -qi "滑块\|验证码\|captcha\|人机\|robot\|verify\|challenge"; then
    echo "检测到反爬校验"
fi
```

### 处理流程

```bash
# 1. 截图展示给用户
python camofox_adapter.py screenshot $TAB_ID --output /tmp/captcha.png --view

# 2. 告知用户
echo "页面出现了验证码/滑块验证，需要你手动处理。"
echo "建议：在真实浏览器中完成验证，然后将 cookies 导出保存。"
echo "或者：告诉我验证完成后，我继续后续操作。"

# 3. 等待用户确认后继续
# ← 此处等待用户回复"完成了"
python camofox_adapter.py snapshot $TAB_ID  # 确认验证已通过
```

### 预防策略

- 使用 `scroll` 命令模拟人类浏览行为（已内置随机滚动）
- 操作之间加适当延迟（`sleep 1~3`）
- 避免过快的连续请求
- 如果网站频繁触发验证，考虑先在真实浏览器登录，再用 `auth_state.py save` 保存状态
