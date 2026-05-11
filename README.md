# AI 智能体技能仓库

这是一个用于管理 AI 智能体技能的 Git 仓库。支持多种智能体（Claude Code、Cursor、Windsurf、Cline），提供交互式安装和批量管理功能。

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

### 支持的智能体

| 智能体 | 安装方式 | 目标路径 |
|--------|----------|----------|
| Claude Code | 符号链接 | `~/.claude/skills/` |
| Cursor | 复制规则文件 | `~/.cursor/rules/` |
| Windsurf | 复制规则文件 | `~/.windsurf/rules/` |
| Cline | 复制规则文件 | `~/.cline/rules/` |

### 使用 Git Bash (Windows)

```bash
cd ~/.claude/skill-repo

# 交互式安装（选择智能体和技能）
bash install.sh install

# 批量安装特定技能到 Cursor
bash install.sh install --agent cursor --skills cn-stock-analysis,mx-data

# 安装所有技能到所有智能体
bash install.sh install --agent all --yes

# 列出可用技能
bash install.sh scan

# 列出已安装的技能
bash install.sh list --agent claude-code

# 卸载技能
bash install.sh uninstall --skills mx-data --agent claude-code
```

### 使用 PowerShell (Windows)

```powershell
cd ~\.claude\skill-repo

# 交互式安装
.\install.ps1 install

# 批量安装
.\install.ps1 install -Agent cursor -Skills cn-stock-analysis,mx-data

# 安装所有
.\install.ps1 install -Agent all -Yes

# 列出可用技能
.\install.ps1 scan

# 列出已安装
.\install.ps1 list -Agent claude-code

# 卸载
.\install.ps1 uninstall -Skills mx-data -Agent claude-code
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `-a, --agent` | 目标智能体：claude-code, cursor, windsurf, cline, all |
| `-s, --skills` | 要安装的技能（逗号分隔） |
| `-y, --yes` | 非交互模式，安装所有技能 |
| `--dry-run` | 显示将要执行的操作，但不实际执行 |

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
├── install.sh           # 安装脚本 (Git Bash)
├── install.ps1          # 安装脚本 (PowerShell)
├── sync.sh              # 多设备同步脚本
├── lib/                 # 共享函数库
│   ├── common.sh        # Bash 共享函数
│   ├── common.ps1       # PowerShell 共享函数
│   └── adapters/        # 智能体适配器
│       ├── claude-code.sh/.ps1
│       ├── cursor.sh/.ps1
│       ├── windsurf.sh/.ps1
│       └── cline.sh/.ps1
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
