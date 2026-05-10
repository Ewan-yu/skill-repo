# 常见问题排查

## 中文乱码

**症状**：`--help` 或进度输出显示 `???`、`锟斤拷` 等乱码。

**原因**：Windows 终端默认编码不是 UTF-8。

**解决**：
1. 脚本已内置 `sys.stdout.reconfigure(encoding="utf-8")`，正常情况应自动处理
2. 如果仍然乱码，在运行前设置环境变量：`set PYTHONUTF8=1`
3. 或在 PowerShell 中：`$env:PYTHONUTF8="1"`
4. 进度信息（stderr）为英文，不受影响；JSON 输出（stdout）使用 `ensure_ascii=False` 保留中文

## camofox-browser 相关

### 服务未就绪 / 自动安装失败

**症状**：`python3 scripts/camofox_adapter.py init` 报错。

**检查**：
1. 确认 `git` 和 `npm` 已安装：`git --version && npm --version`
2. 检查日志：`cat ~/.hermes/logs/camofox-browser.log`
3. 手动启动：`cd ~/.hermes/camofox-browser && npm start`
4. 检查端口占用：`lsof -i :9377`

### Node.js 版本过低

**症状**：npm install 失败，提示语法不支持。

**解决**：安装 Node.js 18+。推荐使用 nvm：
```bash
nvm install 18
nvm use 18
```

### 首次运行下载 CamouFox 引擎很慢

**正常现象**：首次 `npm install` 会下载 CamouFox 浏览器引擎（约 300MB），可能需要几分钟。后续运行不会重复下载。

如果网络受限，可以设置代理：
```bash
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
cd ~/.hermes/camofox-browser && npm install
```

## 脚本执行相关

### 脚本返回错误或空内容

所有脚本返回 JSON 格式，包含 `error` 字段（如有错误）：
- `extract_content.js` 返回 `{"error": "...", "content": ""}` → 页面可能未加载完成或结构已变化
- `extract_images.js` 返回 `{"error": "...", "images": []}` → #js_content 不存在
- `extract_metadata.js` 返回 `{"error": "未能提取标题"}` → 页面结构已变化

处理方式：重新滚动页面等待加载，或检查选择器是否需要更新。

### evaluate 返回结果格式

camofox 的 evaluate 端点返回格式为 `{"ok": true, "result": ...}`。适配器已自动处理解析，直接获取 `result` 内容。

如果手动调用 API，注意解析：
```python
import json, urllib.request
resp = urllib.request.urlopen("http://localhost:9377/tabs/$TAB_ID/evaluate", data=json.dumps({
    "userId": "wxcj",
    "expression": "document.title"
}).encode())
result = json.loads(resp.read())
print(result["result"])  # 这里才是实际结果
```

### 图片位置不正确

确保使用 `scripts/extract_content.js` 的 TreeWalker 代码提取内容，而不是简单的 `innerText`。TreeWalker 方法按 DOM 顺序遍历，能精确保留图片在原文中的位置。

### 样式未保留

如果某些样式未被识别，可能是因为：
1. 微信使用了非标准标签 + 内联样式的方式
2. 样式是通过 CSS class 应用的

解决方法：检查文章的 HTML 结构，必要时在 `extract_content.js` 的 walk 函数中添加更多的样式检测逻辑。

### 引用块未识别

如果文章中的引用样式未被识别为引用块，可能是因为：
1. 引用块不是标准的 `<blockquote>` 标签
2. 引用块没有明显的左边框样式

解决方法：检查文章的 HTML 结构，查看引用块的实际标签和样式，必要时修改 `isBlockquote` 函数的检测逻辑。

## 图片相关

### Blob URL 图片

微信图片可能使用 `blob:http://` 格式，这是懒加载机制。通过 camofox 滚动 + `data-src` 提取可获取真实 URL。Camoufox 作为真实浏览器，滚动后 `data-src` 会自动变成 `src`，脚本的 `node.getAttribute("data-src") || node.src` 逻辑兼容此行为。

### 图片下载失败

检查：
1. URL 是否完整（不含 `#imgIndex` 后缀）
2. 文件大小是否 >0 字节
3. 重新滚动页面后再次提取

### 中文路径问题

图片文件夹使用 `序号_拼音首字母` 格式避免中文路径识别问题。

## Obsidian 双链相关

### 双链未生效

**症状**：文章中的内链显示为 `[链接文字](URL)` 而非 `[[文章标题]]`。

**原因**：`window.__urlMap` 未正确注入，或文章的 `mid` 参数不在映射表中。

**处理**：
1. 确认使用了 `--url-map` 参数：`python3 scripts/camofox_adapter.py eval $TAB_ID scripts/extract_content.js --url-map urlmap.json`
2. 检查 urlmap.json 文件格式是否正确（JSON 对象，key 为完整微信 URL）
3. 确认目标文章已在目录索引中标记为 `✅ 已采集`
4. 确认 urlMap 的 key 是完整的微信 URL（包含 `mid=` 参数）

### 断点续采

批量采集时，如果中断后需要继续：
1. 读取目录索引文件，检查哪些文章状态为 `待采集`
2. 从第一个 `待采集` 的文章开始继续
3. 每完成一篇立即更新目录索引状态为 `✅ 已采集`

## 反爬虫相关问题

### 出现验证码

**症状**：页面弹出验证码、滑块验证或"环境异常"提示。

**处理**：
1. 立即停止采集，关闭 tab
2. 手动在浏览器中完成验证码验证
3. 等待 2-3 分钟后重新开始
4. 降低后续采集频率（文章间延迟增加到 8-15 秒）

注意：使用 Camoufox 后，触发验证码的概率已大幅降低，因为指纹伪装在 C++ 层面完成。

### 页面加载超时

**症状**：文章页面长时间加载不出内容。

**处理**：
1. 检查网络连接
2. 等待 10-15 秒后重试
3. 如果连续 3 次失败，休息 2 分钟再继续

### 图片全部加载失败

**症状**：所有图片都显示为占位符或下载为空文件。

**处理**：
1. 检查是否触发了频率限制
2. 增大图片下载间隔到 2-3 秒
3. 确保在 tab 关闭前完成图片下载

### 采集速度过快被限制

**症状**：文章内容提取返回空或异常。

**处理**：
1. 立即停止，休息 3-5 分钟
2. 将批次大小从 5 篇减少到 3 篇
3. 增大文章间延迟到 10-15 秒
4. 参考 `references/anti-crawling.md` 调整参数
