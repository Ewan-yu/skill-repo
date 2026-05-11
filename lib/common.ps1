# common.ps1 - PowerShell 共享函数库
# 提供技能发现、元数据解析、配置管理、交互式菜单等功能

$ErrorActionPreference = "Stop"

# 仓库根目录
$Script:RepoDir = Split-Path -Parent $PSScriptRoot
$Script:SkillsDir = Join-Path $Script:RepoDir "skills"
$Script:ConfigFile = Join-Path $Script:RepoDir "install-config.json"
$Script:InstallLog = Join-Path $Script:RepoDir ".install-log"

# 回滚栈
$Script:RollbackStack = @()

# ============================================================================
# 技能发现
# ============================================================================

function Scan-Skills {
    <#
    .SYNOPSIS
    扫描所有可用技能
    #>
    $excludePatterns = @('*-workspace', '*.old', '*.bak')

    Get-ChildItem -Path $Script:SkillsDir -Directory | ForEach-Object {
        $name = $_.Name

        # 排除模式匹配
        foreach ($pattern in $excludePatterns) {
            if ($name -like $pattern) { return }
        }

        # 必须有 SKILL.md
        $skillFile = Join-Path $_.FullName "SKILL.md"
        if (Test-Path $skillFile) {
            $name
        }
    }
}

function Get-SkillCount {
    (Scan-Skills | Measure-Object).Count
}

# ============================================================================
# 元数据解析
# ============================================================================

function Parse-SkillMeta {
    <#
    .SYNOPSIS
    解析 SKILL.md frontmatter
    #>
    param(
        [string]$SkillDir
    )

    $skillFile = Join-Path $SkillDir "SKILL.md"

    if (-not (Test-Path $skillFile)) {
        return $null
    }

    $content = Get-Content $skillFile -Raw

    # 提取 frontmatter
    if ($content -match '(?s)^---\r?\n(.+?)\r?\n---') {
        $frontmatter = $Matches[1]
    } else {
        return $null
    }

    # 解析各个字段
    $result = @{}

    if ($frontmatter -match '(?m)^name:\s*(.+)') {
        $result['name'] = $Matches[1].Trim('"').Trim("'")
    }

    if ($frontmatter -match '(?m)^version:\s*(.+)') {
        $result['version'] = $Matches[1].Trim('"').Trim("'")
    }

    if ($frontmatter -match '(?m)^display_name:\s*(.+)') {
        $result['display_name'] = $Matches[1].Trim('"').Trim("'")
    }

    # description 可能是多行
    if ($frontmatter -match '(?s)(?m)^description:\s*(.+)') {
        $desc = $Matches[1].Split("`n")[0].Trim('"').Trim("'")
        if ($desc.Length -gt 60) {
            $desc = $desc.Substring(0, 60) + "..."
        }
        $result['description'] = $desc
    }

    # 解析 required_env_vars
    $envVars = @()
    if ($frontmatter -match '(?s)(?m)^required_env_vars:\s*\[(.*?)\]') {
        $envVars = $Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ }
    }
    $result['required_env_vars'] = $envVars

    # 如果没有 version，尝试从 _meta.json 获取
    if (-not $result['version']) {
        $metaFile = Join-Path $SkillDir "_meta.json"
        if (Test-Path $metaFile) {
            $meta = Get-Content $metaFile -Raw | ConvertFrom-Json
            if ($meta.version) {
                $result['version'] = $meta.version
            }
        }
    }

    return $result
}

function Test-EnvVar {
    <#
    .SYNOPSIS
    检查环境变量是否已设置
    #>
    param([string]$VarName)

    $value = [Environment]::GetEnvironmentVariable($VarName)
    return [bool]($value -and $value.Length -gt 0)
}

function Get-MissingEnvVars {
    <#
    .SYNOPSIS
    获取缺失的环境变量列表
    #>
    param([string]$SkillDir)

    $meta = Parse-SkillMeta -SkillDir $SkillDir
    if (-not $meta -or -not $meta.required_env_vars) {
        return @()
    }

    $missing = @()
    foreach ($var in $meta.required_env_vars) {
        if (-not (Test-EnvVar -VarName $var)) {
            $missing += $var
        }
    }

    return $missing
}

# ============================================================================
# 配置文件管理
# ============================================================================

function Get-Config {
    <#
    .SYNOPSIS
    加载配置文件
    #>
    if (-not (Test-Path $Script:ConfigFile)) {
        return @{
            version = 1
            agents = @{}
            last_installed = $null
        }
    }

    return Get-Content $Script:ConfigFile -Raw | ConvertFrom-Json
}

function Save-Config {
    <#
    .SYNOPSIS
    保存配置文件
    #>
    param($Config)

    $Config | ConvertTo-Json -Depth 10 | Set-Content $Script:ConfigFile
}

function Get-InstalledSkills {
    <#
    .SYNOPSIS
    获取指定智能体的已安装技能列表
    #>
    param([string]$Agent)

    $config = Get-Config
    if ($config.agents -and $config.agents.$Agent) {
        return $config.agents.$Agent.skills
    }
    return @()
}

function Test-SkillInstalled {
    <#
    .SYNOPSIS
    检查技能是否已安装
    #>
    param(
        [string]$Agent,
        [string]$Skill
    )

    $installed = Get-InstalledSkills -Agent $Agent
    return $installed -contains $Skill
}

function Add-ToConfig {
    <#
    .SYNOPSIS
    添加技能到配置
    #>
    param(
        [string]$Agent,
        [string]$Skill
    )

    $config = Get-Config

    if (-not $config.agents) {
        $config | Add-Member -NotePropertyName "agents" -NotePropertyValue @{} -Force
    }

    if (-not $config.agents.$Agent) {
        $config.agents | Add-Member -NotePropertyName $Agent -NotePropertyValue @{
            enabled = $true
            skills = @()
        } -Force
    }

    $skills = @($config.agents.$Agent.skills)
    if ($skills -notcontains $Skill) {
        $skills += $Skill
        $config.agents.$Agent.skills = $skills
    }

    Save-Config -Config $config
}

function Remove-FromConfig {
    <#
    .SYNOPSIS
    从配置中移除技能
    #>
    param(
        [string]$Agent,
        [string]$Skill
    )

    $config = Get-Config

    if ($config.agents -and $config.agents.$Agent -and $config.agents.$Agent.skills) {
        $skills = @($config.agents.$Agent.skills) | Where-Object { $_ -ne $Skill }
        $config.agents.$Agent.skills = $skills
        Save-Config -Config $config
    }
}

# ============================================================================
# 交互式菜单
# ============================================================================

function Show-SkillMenu {
    <#
    .SYNOPSIS
    显示技能选择菜单
    #>
    param([string]$Agent)

    $skills = @(Scan-Skills)

    if ($skills.Count -eq 0) {
        Write-Host "No skills found" -ForegroundColor Red
        return @()
    }

    # 获取已安装的技能
    $installed = @(Get-InstalledSkills -Agent $Agent)

    # 选择状态数组
    $selected = @{}
    foreach ($skill in $skills) {
        $selected[$skill] = $installed -contains $skill
    }

    while ($true) {
        # 清屏并显示菜单
        Clear-Host
        Write-Host "=== Skill Installer v2.0 ===" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Agent: " -NoNewline
        Write-Host $Agent -ForegroundColor Green
        Write-Host ""
        Write-Host "Available skills:" -ForegroundColor Yellow

        for ($i = 0; $i -lt $skills.Count; $i++) {
            $skill = $skills[$i]
            $mark = if ($selected[$skill]) { "x" } else { " " }

            $meta = Parse-SkillMeta -SkillDir (Join-Path $Script:SkillsDir $skill)
            $version = if ($meta.version) { $meta.version } else { "unknown" }
            $desc = if ($meta.description) { $meta.description } else { "" }

            # 检查缺失的环境变量
            $envHint = ""
            $missing = @(Get-MissingEnvVars -SkillDir (Join-Path $Script:SkillsDir $skill))
            if ($missing.Count -gt 0) {
                $envHint = " " + "(needs: $($missing -join ', '))"
            }

            Write-Host "  [$mark] " -NoNewline
            Write-Host ("{0,2}. " -f ($i + 1)) -NoNewline
            Write-Host ("{0,-25}" -f $skill) -NoNewline
            Write-Host ("v{0,-10}" -f $version) -NoNewline
            Write-Host "$desc$envHint"
        }

        Write-Host ""
        Write-Host "Toggle: 1-$($skills.Count)  |  [a] Select all  [n] Deselect all  [q] Confirm" -ForegroundColor Cyan
        Write-Host -NoNewline "> "
        Write-Host -ForegroundColor Green -NoNewline ""

        $key = [Console]::ReadKey($true).KeyChar

        switch ($key) {
            { $_ -in 'q', 'Q', "`n", "" } { break }
            { $_ -in 'a', 'A' } {
                for ($i = 0; $i -lt $skills.Count; $i++) {
                    $selected[$skills[$i]] = $true
                }
            }
            { $_ -in 'n', 'N' } {
                for ($i = 0; $i -lt $skills.Count; $i++) {
                    $selected[$skills[$i]] = $false
                }
            }
            default {
                if ($key -match '^\d+$') {
                    $idx = [int]$key - 1
                    if ($idx -ge 0 -and $idx -lt $skills.Count) {
                        $selected[$skills[$idx]] = -not $selected[$skills[$idx]]
                    }
                }
            }
        }

        if ($key -in 'q', 'Q', "`n", "") { break }
    }

    # 返回选中的技能
    return $skills | Where-Object { $selected[$_] }
}

function Confirm-Action {
    <#
    .SYNOPSIS
    确认对话框
    #>
    param(
        [string]$Prompt,
        [bool]$Default = $true
    )

    if ($Default) {
        Write-Host "$Prompt [Y/n]: " -NoNewline
    } else {
        Write-Host "$Prompt [y/N]: " -NoNewline
    }

    $key = [Console]::ReadKey($true).KeyChar
    Write-Host ""

    switch ($key) {
        { $_ -in 'y', 'Y', "`n", "" } { return $Default }
        { $_ -in 'n', 'N' } { return (-not $Default) }
        default { return $Default }
    }
}

# ============================================================================
# 回滚机制
# ============================================================================

function Push-Rollback {
    <#
    .SYNOPSIS
    添加回滚操作
    #>
    param([string]$Command)

    $Script:RollbackStack += $Command
}

function Invoke-Rollback {
    <#
    .SYNOPSIS
    执行回滚
    #>
    if ($Script:RollbackStack.Count -eq 0) {
        return
    }

    Write-Host "Rolling back..." -ForegroundColor Yellow
    for ($i = $Script:RollbackStack.Count - 1; $i -ge 0; $i--) {
        try {
            Invoke-Expression $Script:RollbackStack[$i] 2>$null
        } catch {
            # Ignore rollback errors
        }
    }
    $Script:RollbackStack = @()
    Write-Host "Rollback complete" -ForegroundColor Yellow
}

function Clear-Rollback {
    $Script:RollbackStack = @()
}

# ============================================================================
# 日志记录
# ============================================================================

function Write-LogOperation {
    <#
    .SYNOPSIS
    记录安装操作
    #>
    param(
        [string]$Action,
        [string]$Src,
        [string]$Dst,
        [bool]$Success
    )

    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $entry = @{
        timestamp = $timestamp
        action = $Action
        src = $Src
        dst = $Dst
        success = $Success
    }

    $entry | ConvertTo-Json -Compress | Add-Content $Script:InstallLog
}

# ============================================================================
# 工具函数
# ============================================================================

function Write-Success {
    param([string]$Message)
    Write-Host "  OK $Message" -ForegroundColor Green
}

function Write-Warning2 {
    param([string]$Message)
    Write-Host "  ! $Message" -ForegroundColor Yellow
}

function Write-Error2 {
    param([string]$Message)
    Write-Host "  X $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "  i $Message" -ForegroundColor Blue
}
