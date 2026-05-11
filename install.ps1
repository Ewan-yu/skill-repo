# install.ps1 - 技能安装脚本 v2.0 (PowerShell)
# 支持多智能体、交互式选择、批量安装

param(
    [Parameter(Position=0)]
    [ValidateSet("install", "uninstall", "list", "scan")]
    [string]$Action = "install",

    [string]$Agent,
    [string[]]$Skills,
    [switch]$Yes,
    [switch]$DryRun,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# 脚本目录
$ScriptDir = $PSScriptRoot

# 加载共享函数
. "$ScriptDir\lib\common.ps1"

# ============================================================================
# 帮助信息
# ============================================================================

function Show-Help {
    @"

Skill Installer v2.0 (PowerShell)

Usage: install.ps1 [action] [options]

Actions:
  install     Install selected skills (default)
  uninstall   Uninstall installed skills
  list        List installed skills
  scan        List all available skills

Options:
  -Agent <agent>       Target agent: claude-code, cursor, windsurf, cline, all
  -Skills <names>      Skills to install (comma-separated)
  -Yes                 Non-interactive mode, install all skills
  -DryRun              Show what would be done without doing it
  -Help                Show this help

Examples:
  .\install.ps1 install -Agent claude-code
  .\install.ps1 install -Agent cursor -Skills cn-stock-analysis,mx-data
  .\install.ps1 install -Agent all -Yes
  .\install.ps1 uninstall -Skills mx-data -Agent all
  .\install.ps1 list -Agent claude-code
  .\install.ps1 scan

"@
}

# ============================================================================
# 智能体管理
# ============================================================================

function Get-AllAgents {
    return @("claude-code", "cursor", "windsurf", "cline")
}

function Load-Adapter {
    param([string]$Agent)

    $adapterFile = Join-Path $ScriptDir "lib\adapters\$Agent.ps1"

    if (-not (Test-Path $adapterFile)) {
        Write-Error2 "Unsupported agent: $Agent"
        return $false
    }

    . $adapterFile
    return $true
}

function Select-Agent {
    param([string]$AgentParam)

    if ($AgentParam) {
        $validAgents = Get-AllAgents
        if ($validAgents -notcontains $AgentParam) {
            Write-Error2 "Unsupported agent: $AgentParam"
            Write-Host "Supported agents: $($validAgents -join ', ')"
            exit 1
        }
        return $AgentParam
    }

    # 交互式选择
    Write-Host "Select agent:" -ForegroundColor Cyan
    Write-Host "  1. Claude Code"
    Write-Host "  2. Cursor"
    Write-Host "  3. Windsurf"
    Write-Host "  4. Cline"
    Write-Host "  5. All"
    Write-Host ""
    Write-Host -NoNewline "> "
    Write-Host -ForegroundColor Green -NoNewline ""

    $key = [Console]::ReadKey($true).KeyChar
    Write-Host ""

    switch ($key) {
        '1' { return "claude-code" }
        '2' { return "cursor" }
        '3' { return "windsurf" }
        '4' { return "cline" }
        '5' { return "all" }
        default {
            Write-Error2 "Invalid choice"
            exit 1
        }
    }
}

# ============================================================================
# 安装操作
# ============================================================================

function Install-SkillToAgent {
    param(
        [string]$Skill,
        [string]$Agent,
        [bool]$DryRun = $false
    )

    $src = Join-Path $ScriptDir "skills\$Skill"

    Load-Adapter -Agent $Agent | Out-Null

    if ($DryRun) {
        Write-Info "[DRY RUN] Will install: $Skill -> $(Get-AdapterTarget)"
        return $true
    }

    $result = Install-AdapterSkill -Src $src -Name $Skill

    if ($result) {
        Add-ToConfig -Agent $Agent -Skill $Skill
    }

    return $result
}

function Uninstall-SkillFromAgent {
    param(
        [string]$Skill,
        [string]$Agent,
        [bool]$DryRun = $false
    )

    Load-Adapter -Agent $Agent | Out-Null

    if ($DryRun) {
        Write-Info "[DRY RUN] Will uninstall: $Skill"
        return $true
    }

    $result = Uninstall-AdapterSkill -Name $Skill

    if ($result) {
        Remove-FromConfig -Agent $Agent -Skill $Skill
    }

    return $result
}

function Install-ToAllAgents {
    param(
        [string[]]$Skills,
        [bool]$DryRun = $false
    )

    $agents = Get-AllAgents

    foreach ($agent in $agents) {
        Write-Host ""
        Write-Host "Installing to $agent :" -ForegroundColor Cyan
        foreach ($skill in $Skills) {
            Install-SkillToAgent -Skill $skill -Agent $agent -DryRun $DryRun | Out-Null
        }
    }
}

function Uninstall-FromAllAgents {
    param(
        [string[]]$Skills,
        [bool]$DryRun = $false
    )

    $agents = Get-AllAgents

    foreach ($agent in $agents) {
        Write-Host ""
        Write-Host "Uninstalling from $agent :" -ForegroundColor Cyan
        foreach ($skill in $Skills) {
            Uninstall-SkillFromAgent -Skill $skill -Agent $agent -DryRun $DryRun | Out-Null
        }
    }
}

# ============================================================================
# 主流程
# ============================================================================

function Invoke-Install {
    param(
        [string]$Agent,
        [string[]]$Skills,
        [bool]$YesMode = $false,
        [bool]$DryRun = $false
    )

    $selectedAgent = Select-Agent -AgentParam $Agent

    # 如果没有指定技能，进入交互模式
    if ($Skills.Count -eq 0) {
        if ($YesMode) {
            # 非交互模式：选择所有技能
            $Skills = @(Scan-Skills)
        } else {
            # 交互模式：显示菜单
            if ($selectedAgent -eq "all") {
                $Skills = @(Show-SkillMenu -Agent "claude-code")
            } else {
                $Skills = @(Show-SkillMenu -Agent $selectedAgent)
            }
        }
    }

    if ($Skills.Count -eq 0) {
        Write-Warning2 "No skills selected"
        return
    }

    Write-Host ""
    Write-Host "Ready to install $($Skills.Count) skills:" -ForegroundColor Cyan
    foreach ($skill in $Skills) {
        Write-Host "  - $skill"
    }

    if ($DryRun) {
        Write-Host ""
        Write-Info "[DRY RUN] The above operations would be executed, but nothing was done."
        return
    }

    if (-not $YesMode) {
        Write-Host ""
        if (-not (Confirm-Action "Confirm install?" $true)) {
            Write-Warning2 "Cancelled"
            return
        }
    }

    Write-Host ""

    if ($selectedAgent -eq "all") {
        Install-ToAllAgents -Skills $Skills -DryRun $DryRun
    } else {
        foreach ($skill in $Skills) {
            Install-SkillToAgent -Skill $skill -Agent $selectedAgent -DryRun $DryRun | Out-Null
        }
    }

    Write-Host ""
    Write-Success "Installation complete!"

    # 显示环境变量提示
    $envHintShown = $false
    foreach ($skill in $Skills) {
        $missing = @(Get-MissingEnvVars -SkillDir (Join-Path $ScriptDir "skills\$skill"))
        if ($missing.Count -gt 0) {
            if (-not $envHintShown) {
                Write-Host ""
                Write-Host "Note: The following skills require environment variables:" -ForegroundColor Yellow
                $envHintShown = $true
            }
            $missingStr = $missing -join ', '
            Write-Host "  $skill : $missingStr"
        }
    }

    if ($envHintShown) {
        Write-Host ""
        Write-Host "Please ensure the above environment variables are set."
    }
}

function Invoke-Uninstall {
    param(
        [string]$Agent,
        [string[]]$Skills,
        [bool]$YesMode = $false,
        [bool]$DryRun = $false
    )

    $selectedAgent = Select-Agent -AgentParam $Agent

    if ($Skills.Count -eq 0) {
        Write-Error2 "Please specify skills to uninstall (-Skills)"
        exit 1
    }

    Write-Host ""
    Write-Host "Ready to uninstall $($Skills.Count) skills:" -ForegroundColor Cyan
    foreach ($skill in $Skills) {
        Write-Host "  - $skill"
    }

    if (-not $YesMode) {
        Write-Host ""
        if (-not (Confirm-Action "Confirm uninstall?" $false)) {
            Write-Warning2 "Cancelled"
            return
        }
    }

    Write-Host ""

    if ($selectedAgent -eq "all") {
        Uninstall-FromAllAgents -Skills $Skills -DryRun $DryRun
    } else {
        foreach ($skill in $Skills) {
            Uninstall-SkillFromAgent -Skill $skill -Agent $selectedAgent -DryRun $DryRun | Out-Null
        }
    }

    Write-Host ""
    Write-Success "Uninstall complete!"
}

function Invoke-List {
    param([string]$Agent)

    $selectedAgent = Select-Agent -AgentParam $Agent

    Write-Host ""
    Write-Host "Installed skills ($selectedAgent):" -ForegroundColor Cyan

    if ($selectedAgent -eq "all") {
        $agents = Get-AllAgents
        foreach ($agent in $agents) {
            Load-Adapter -Agent $agent | Out-Null
            $target = Get-AdapterTarget
            Write-Host ""
            Write-Host "$agent ($target):" -ForegroundColor Yellow
            $installed = @(Get-AdapterInstalledSkills 2>$null)
            if ($installed.Count -eq 0) {
                Write-Host "  (none)"
            } else {
                foreach ($item in $installed) {
                    Write-Host "  - $item"
                }
            }
        }
    } else {
        Load-Adapter -Agent $selectedAgent | Out-Null
        $target = Get-AdapterTarget
        Write-Host "Target directory: $target" -ForegroundColor Yellow
        $installed = @(Get-AdapterInstalledSkills 2>$null)
        if ($installed.Count -eq 0) {
            Write-Host "  (none)"
        } else {
            foreach ($item in $installed) {
                Write-Host "  - $item"
            }
        }
    }
}

function Invoke-Scan {
    Write-Host ""
    Write-Host "Available skills:" -ForegroundColor Cyan
    Write-Host ""

    $skills = @(Scan-Skills)
    $count = 0

    foreach ($skill in $skills) {
        $count++
        $meta = Parse-SkillMeta -SkillDir (Join-Path $ScriptDir "skills\$skill")

        $version = if ($meta.version) { $meta.version } else { "unknown" }
        $desc = if ($meta.description) { $meta.description } else { "" }
        $displayName = if ($meta.display_name) { $meta.display_name } else { "" }

        Write-Host ("  {0,2}. {1,-25}" -f $count, $skill) -NoNewline

        if ($displayName -and $displayName -ne $skill) {
            Write-Host " $displayName" -NoNewline
        }

        if ($version -and $version -ne "unknown") {
            Write-Host " v$version" -NoNewline
        }

        Write-Host ""

        if ($desc) {
            Write-Host "      $desc"
        }

        $missing = @(Get-MissingEnvVars -SkillDir (Join-Path $ScriptDir "skills\$skill"))
        if ($missing.Count -gt 0) {
            $missingStr = $missing -join ', '
            Write-Host "      Requires: $missingStr" -ForegroundColor Yellow
        }

        Write-Host ""
    }

    $countStr = "$count"
    Write-Host "Total: $count skills" -ForegroundColor Blue
}

# ============================================================================
# 入口
# ============================================================================

if ($Help) {
    Show-Help
    exit 0
}

$yesMode = $Yes -eq $true
$dryRun = $DryRun -eq $true

switch ($Action) {
    "install" {
        Invoke-Install -Agent $Agent -Skills $Skills -YesMode $yesMode -DryRun $dryRun
    }
    "uninstall" {
        Invoke-Uninstall -Agent $Agent -Skills $Skills -YesMode $yesMode -DryRun $dryRun
    }
    "list" {
        Invoke-List -Agent $Agent
    }
    "scan" {
        Invoke-Scan
    }
    default {
        Write-Error2 "Unknown action: $Action"
        Show-Help
        exit 1
    }
}
