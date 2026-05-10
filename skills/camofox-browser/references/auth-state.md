# 登录状态管理

## 状态文件格式

```json
{
  "saved_at": "2026-05-10T14:30:00+00:00",
  "url": "https://example.com/dashboard",
  "domain": "example.com",
  "cookies": {
    "session_id": "abc123def456",
    "user_token": "bearer xyz"
  },
  "localStorage": {
    "user_id": "12345",
    "auth_token": "eyJhbGciOiJIUzI1NiJ9...",
    "preferences": "{\"theme\":\"dark\"}"
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `saved_at` | string | 保存时间（ISO 8601） |
| `url` | string | 保存时的页面 URL |
| `domain` | string | 保存时的域名 |
| `cookies` | object | 键值对形式的 cookies |
| `localStorage` | object | 键值对形式的 localStorage 数据 |

## 保存机制

通过 JavaScript 在页面上下文中执行：

```javascript
// 提取 cookies
document.cookie.split('; ').reduce((acc, c) => {
    const [k, ...v] = c.split('=');
    acc[k] = v.join('=');
    return acc;
}, {})

// 提取 localStorage
const data = {};
for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    data[key] = localStorage.getItem(key);
}
```

## 恢复机制

通过 JavaScript 注入到新页面：

```javascript
// 恢复 cookies
document.cookie = 'key=value; path=/; max-age=31536000';

// 恢复 localStorage
localStorage.setItem('key', 'value');
```

## 已知限制

### httpOnly Cookies

`document.cookie` **无法**访问标记为 `httpOnly` 的 cookies。这是浏览器安全限制，无法绕过。

**影响**：如果网站将认证 token 存储在 httpOnly cookie 中（如 `session_id`），则无法通过此方式保存完整的登录状态。

**解决方案**：
1. 如果网站在 localStorage 中也存储了 token，可以保存 localStorage 部分
2. 如果只有 httpOnly cookie，需要每次重新登录
3. 检查网站的认证机制：查看登录后 cookies 和 localStorage 中哪些字段包含认证信息

### 跨域 Cookies

`document.cookie` 只能访问当前域名的 cookies。如果登录流程涉及 SSO 跳转（如 `auth.example.com` → `app.example.com`），需要在最终域名上保存状态。

### Cookie 域名和路径

恢复 cookies 时使用 `path=/`，适用于大多数场景。如果网站使用了特殊的 path 或 domain 设置，可能需要调整恢复脚本。

## 安全注意事项

1. **不要提交到 Git**：状态文件包含认证信息，应添加到 `.gitignore`
2. **文件权限**：确保状态文件只有当前用户可读
3. **加密存储**（可选）：对敏感场景，可以使用系统密钥管理器加密状态文件
4. **定期更新**：token 通常有过期时间，定期检查并更新保存的状态

## 状态验证

使用 `check` 命令验证当前页面的登录状态：

```bash
python3 scripts/auth_state.py check $TAB_ID
```

返回：

```json
{
  "hasCookies": true,
  "cookieCount": 5,
  "localStorageCount": 12,
  "url": "https://example.com/dashboard",
  "title": "Dashboard - Example"
}
```

如果 `cookieCount` 和 `localStorageCount` 都为 0，说明登录状态可能已失效。

## 命名约定

建议按域名组织状态文件：

```
auth_states/
├── github.com.json
├── zsxq.com.json
├── example.com.json
└── ...
```

或者使用完整的域名+路径：

```
auth_states/
├── wx.zsxq.com_group_28885122181251.json
└── ...
```
