# Claude Code 自定义技能仓库

这是一个用于管理 Claude Code 自定义技能的 Git 仓库。所有技能都通过符号链接安装到 `~/.claude/skills/` 目录。

## 包含的技能

| 技能名 | 描述 | 版本 |
|--------|------|------|
| camofox-browser | 通用浏览器自动化 | 1.0.0 |
| cn-stock-analysis | A股基本面分析 | 2.2 |
| mx-data | 东方财富金融数据查询 | 1.0.5 |
| mx-moni | 模拟组合管理 | 1.0.4 |
| mx-search | 金融资讯搜索 | 1.0.5 |
| mx-xuangu | 智能选股 | 1.0.4 |
| mx-zixuan | 自选股管理 | 1.0.0 |
| stock-valuation | 股票估值分析 | 1.0.0 |
| wxcj | 微信公众号文章采集 | 1.0.0 |

## 安装方法

### 使用 Git Bash (Windows)

```bash
cd ~/.claude/skill-repo
bash install.sh
```

### 使用 PowerShell (Windows)

```powershell
cd ~\.claude\skill-repo
.\install.ps1
```

## 同步更新

当仓库有更新时，运行同步脚本：

```bash
cd ~/.claude/skill-repo
bash sync.sh
```

## 安全说明

本仓库为公开仓库，已采取以下安全措施：

1. **API 密钥管理**：所有 API 密钥通过环境变量配置，不存储在代码中
2. **配置文件隔离**：`settings.json` 等配置文件已添加到 `.gitignore`
3. **预提交检查**：配置了 pre-commit hook，自动检测敏感信息泄露
4. **定期扫描**：提供 `scripts/security-scan.sh` 脚本，定期扫描仓库

### 如何添加 API 密钥

1. 在你的设备上设置环境变量：
   ```bash
   export MX_APIKEY=your_api_key_here
   ```

2. 或在 `~/.claude/settings.json` 中配置（此文件不会被提交）：
   ```json
   {
     "env": {
       "MX_APIKEY": "your_api_key_here"
     }
   }
   ```

### 发现安全问题

如果发现仓库中存在敏感信息泄露，请立即：
1. 在 GitHub 上提交 Issue（标记为 security）
2. 联系仓库维护者
3. 轮换泄露的密钥

## 开发工作流

### 创建新技能

1. 运行 `/skill-creator` 启动技能创建流程
2. 按照 skill-creator 引导完成技能开发
3. 技能就绪后移入仓库：
   ```bash
   mv ~/.claude/skills/new-skill ~/.claude/skill-repo/skills/new-skill
   ln -s ~/.claude/skill-repo/skills/new-skill ~/.claude/skills/new-skill
   ```
4. 提交到 Git

### 编辑现有技能

直接在仓库目录中编辑，通过符号链接实时生效：

```bash
vim ~/.claude/skill-repo/skills/cn-stock-analysis/SKILL.md

cd ~/.claude/skill-repo
git add skills/cn-stock-analysis/SKILL.md
git commit -m "feat(cn-stock-analysis): 更新估值分析方法"
```

### 测试技能

使用 skill-creator 的评估工具：

```bash
cd ~/.claude/skill-repo/skills/cn-stock-analysis
python ~/.agents/skills/skill-creator/scripts/run_eval.py .
```

或直接在 Claude Code 中使用技能验证行为。

### 打包发布

```bash
cd ~/.claude/skill-repo
bash packages/build-all.sh

git add packages/
git commit -m "chore: 构建 v2.2 技能包"
git tag cn-stock-analysis/v2.2
git push origin main --tags
```

## 目录结构

```
skill-repo/
├── .gitignore           # Git 忽略规则（安全优先）
├── README.md            # 本文件
├── install.sh           # 符号链接安装脚本 (Git Bash)
├── install.ps1          # 符号链接安装脚本 (PowerShell)
├── sync.sh              # 多设备同步脚本
├── scripts/
│   └── security-scan.sh # 安全扫描脚本
├── skills/              # 所有技能存放目录
│   ├── camofox-browser/
│   ├── cn-stock-analysis/
│   ├── mx-data/
│   ├── mx-moni/
│   ├── mx-search/
│   ├── mx-xuangu/
│   ├── mx-zixuan/
│   ├── stock-valuation/
│   └── wxcj/
└── packages/            # 打包输出目录（.gitignore）
    └── *.skill
```

## Git 规范

### 提交规范

使用 Conventional Commits 格式，提交信息用中文：

```
feat(技能名): 描述新增功能
fix(技能名): 描述修复内容
docs(技能名): 描述文档更新
refactor(技能名): 描述重构内容
chore: 描述仓库维护操作
```

### 版本标签

按技能打标签追踪发布状态：

```bash
git tag cn-stock-analysis/v2.2
git tag mx-data/v1.0.5
git tag stock-valuation/v1.0.0
```

## 许可证

MIT License
