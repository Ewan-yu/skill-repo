# 登录流程详解

本文档详细描述 camofox-browser 处理各种登录场景的标准流程。

## 目录

1. [二维码登录](#二维码登录)
2. [表单登录](#表单登录)
3. [同意弹窗处理](#同意弹窗处理)
4. [OAuth/SSO 登录](#oauthsso-登录)
5. [验证码处理](#验证码处理)
6. [多步骤登录](#多步骤登录)

---

## 二维码登录

### 检测方式

通过 snapshot 或截图识别页面中的二维码元素：

```bash
# 检查是否有 QR 相关元素
python3 scripts/camofox_adapter.py eval $TAB_ID \
  'JSON.stringify({
    hasQrImg: !!document.querySelector("img[src*=qr], img[alt*=二维码], img[alt*=QR]"),
    hasQrContainer: !!document.querySelector("[class*=qr], [class*=QR], [id*=qr]"),
    bodyText: document.body.innerText.substring(0, 500)
  })'
```

### 标准流程

1. **先处理所有同意弹窗**（见下方"同意弹窗处理"），确保二维码区域不被遮挡
2. **打开登录页** → 等待 3 秒
3. **截图并打开查看器**（唯一需要截图的场景）→ 使用 `--view` 参数，让用户看到二维码：
   ```bash
   python3 scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/qr.png --view
   ```
4. **告知用户**："请扫描截图中的二维码"
5. **轮询检查**（每 5 秒检测一次，最多 24 次 = 120 秒）— **不截图**，用 `eval` 检测 URL 变化：
   - 检查 URL 是否变化（从 /login 跳转到首页）
   - 如果二维码过期（通常 60-120 秒），需要重新触发

### 二维码过期处理

```bash
# 检测是否过期（snapshot 中出现"已过期"、"刷新"等文字）
python3 scripts/camofox_adapter.py snapshot $TAB_ID | grep -i "过期\|刷新\|expire\|refresh"

# 如果过期，点击刷新按钮，然后重新展示二维码给用户
python3 scripts/camofox_adapter.py click $TAB_ID --text "刷新"
sleep 2
python3 scripts/camofox_adapter.py screenshot $TAB_ID --output /tmp/qr_refreshed.png --view
```

### 轮询检查脚本

```bash
TAB_ID=$1
MAX_ATTEMPTS=24
for i in $(seq 1 $MAX_ATTEMPTS); do
    sleep 5
    # 检查 URL 是否已离开登录页
    URL=$(python3 scripts/camofox_adapter.py eval $TAB_ID "location.href")
    if echo "$URL" | grep -qv "login"; then
        echo "Login successful!"
        break
    fi
    echo "Waiting for scan... ($i/$MAX_ATTEMPTS)"
done
```

---

## 表单登录

### 检测方式

```bash
python3 scripts/camofox_adapter.py eval $TAB_ID \
  'JSON.stringify({
    inputs: Array.from(document.querySelectorAll("input")).map(i => ({
      type: i.type, name: i.name, id: i.id, placeholder: i.placeholder
    })),
    buttons: Array.from(document.querySelectorAll("button")).map(b => ({
      text: b.textContent.trim(), type: b.type
    }))
  })'
```

### 标准流程

1. **识别输入字段**：通过 snapshot 或 eval 找到用户名、密码输入框
2. **填写用户名**：
   ```bash
   python3 scripts/camofox_adapter.py type $TAB_ID -s "input[name=username]" -v "user@example.com"
   ```
3. **填写密码**：
   ```bash
   python3 scripts/camofox_adapter.py type $TAB_ID -s "input[name=password]" -v "secret"
   ```
4. **点击登录**：
   ```bash
   python3 scripts/camofox_adapter.py click $TAB_ID -s "button[type=submit]"
   ```
5. **等待并验证**（用 eval 检查 URL，不截图）：
   ```bash
   sleep 3
   python3 scripts/camofox_adapter.py eval $TAB_ID "location.href"
   ```

### React/Vue 框架兼容

adapter 的 `type` 命令使用 `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set` 来设置值，确保触发框架的变更检测。如果某个特殊框架不响应，可以使用更底层的事件模拟：

```bash
python3 scripts/camofox_adapter.py eval $TAB_ID '
  (() => {
    const el = document.querySelector("input[name=q]");
    el.focus();
    el.value = "";
    for (const char of "搜索词") {
      el.value += char;
      el.dispatchEvent(new KeyboardEvent("keydown", {key: char, bubbles: true}));
      el.dispatchEvent(new KeyboardEvent("keypress", {key: char, bubbles: true}));
      el.dispatchEvent(new InputEvent("input", {data: char, inputType: "insertText", bubbles: true}));
      el.dispatchEvent(new KeyboardEvent("keyup", {key: char, bubbles: true}));
    }
    el.dispatchEvent(new Event("change", {bubbles: true}));
  })()
'
```

---

## 同意弹窗处理

> **重要**：同意弹窗必须在所有登录操作之前处理。弹窗会遮挡二维码或表单，导致后续操作失败。打开登录页后，第一步就是检测并处理所有弹窗。

### 常见模式

1. **隐私协议弹窗**：首次访问时弹出，需要点击"同意"
2. **Cookie 同意**：GDPR 相关的 cookie 使用同意
3. **用户协议确认**：注册/登录前的协议确认

### 检测与处理

```bash
# 查找同意相关按钮
python3 scripts/camofox_adapter.py eval $TAB_ID '
  JSON.stringify(
    Array.from(document.querySelectorAll("button, a, span, div"))
      .filter(el => /同意|接受|agree|accept|confirm|确定|OK/i.test(el.textContent.trim()))
      .map(el => ({tag: el.tagName, text: el.textContent.trim().substring(0, 30), class: el.className}))
  )
'

# 点击"同意"
python3 scripts/camofox_adapter.py click $TAB_ID --text "同意"

# 或者通过选择器
python3 scripts/camofox_adapter.py click $TAB_ID -s "button.agree-btn"
```

### 多层弹窗

有些网站会连续弹出多个确认框。处理方式：每次点击后重新 snapshot，检查是否还有新的弹窗。循环处理直到页面干净，再进行后续登录操作。

### 截图原则

弹窗处理过程中的截图不需要打开查看器（用 Read 工具查看即可）。只有最终需要用户操作的截图（如二维码扫码）才使用 `--view` 参数。

---

## OAuth/SSO 登录

### 检测方式

查找第三方登录按钮：

```bash
python3 scripts/camofox_adapter.py eval $TAB_ID '
  JSON.stringify(
    Array.from(document.querySelectorAll("button, a, div[role=button]"))
      .filter(el => /Google|GitHub|WeChat|微信|QQ|Apple|Facebook|Twitter/i.test(el.textContent + el.className))
      .map(el => ({tag: el.tagName, text: el.textContent.trim().substring(0, 50), class: el.className}))
  )
'
```

### 处理方式

OAuth 登录通常会打开新窗口或重定向。camofox-browser 的 tab 会跟随重定向，但弹出窗口可能需要特殊处理。

**推荐方式**：如果用户有该网站的账号，优先使用表单登录而非 OAuth。

---

## 验证码处理

### 检测方式

```bash
python3 scripts/camofox_adapter.py eval $TAB_ID '
  JSON.stringify({
    hasCaptcha: !!document.querySelector("[class*=captcha], [id*=captcha], [class*=verify], iframe[src*=captcha]"),
    bodyText: document.body.innerText.substring(0, 1000)
  })
'
```

### 处理策略

验证码无法自动解决。当检测到验证码时：

1. 截图展示给用户
2. 告知用户："页面出现了验证码，需要你手动处理"
3. 建议用户在真实浏览器中登录，然后保存状态

---

## 多步骤登录

某些网站的登录流程分多步（如：输入手机号 → 获取验证码 → 输入验证码 → 完成）。

### 处理方式

每一步都是一个独立的操作循环：

```bash
# Step 1: 输入手机号
python3 scripts/camofox_adapter.py type $TAB_ID -s "input[name=phone]" -v "13800138000"
python3 scripts/camofox_adapter.py click $TAB_ID --text "获取验证码"

# Step 2: 告知用户查看手机
echo "验证码已发送到手机，请告诉我验证码"

# Step 3: 用户提供验证码后输入
python3 scripts/camofox_adapter.py type $TAB_ID -s "input[name=code]" -v "123456"
python3 scripts/camofox_adapter.py click $TAB_ID -s "button[type=submit]"
```
