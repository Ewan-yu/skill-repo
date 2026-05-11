# claude-code.ps1 - Claude Code 适配器 (PowerShell)
# 安装方式：符号链接到 ~/.claude/skills/

$AdapterTarget = Join-Path $env:USERPROFILE ".claude\skills"
$AdapterName = "claude-code"

function Install-AdapterSkill {
    <#
    .SYNOPSIS
    安装技能
    #>
    param(
        [string]$Src,
        [string]$Name
    )

    $dst = Join-Path $AdapterTarget $Name

    # 确保目标目录存在
    if (-not (Test-Path $AdapterTarget)) {
        New-Item -ItemType Directory -Path $AdapterTarget -Force | Out-Null
    }

    # 检查是否已存在
    if (Test-Path $dst -PathType Leaf) {
        # 符号链接存在
        $currentTarget = (Get-Item $dst).Target
        if ($currentTarget -eq $Src) {
            Write-Info "$Name already installed (symlink)"
            return $true
        } else {
            Write-Warning2 "$Name already exists, pointing to: $currentTarget"
            if (Confirm-Action "Replace with current version?") {
                Remove-Item $dst -Force
            } else {
                return $false
            }
        }
    } elseif (Test-Path $dst -PathType Container) {
        Write-Error2 "$Name already exists as a directory (not a symlink)"
        Write-Host "    Manual migration required:"
        Write-Host "    Remove-Item -Recurse -Force '$dst'; New-Item -ItemType SymbolicLink -Path '$dst' -Target '$Src'"
        return $false
    }

    # 创建符号链接
    try {
        New-Item -ItemType SymbolicLink -Path $dst -Target $Src | Out-Null
        Write-Success "$Name -> $Src"
        Write-LogOperation -Action "symlink" -Src $Src -Dst $dst -Success $true
        Push-Rollback "Remove-Item '$dst' -Force"
        return $true
    } catch {
        Write-Error2 "Failed to create symlink: $Name"
        Write-Host "    Please run with administrator privileges"
        Write-LogOperation -Action "symlink" -Src $Src -Dst $dst -Success $false
        return $false
    }
}

function Uninstall-AdapterSkill {
    <#
    .SYNOPSIS
    卸载技能
    #>
    param([string]$Name)

    $dst = Join-Path $AdapterTarget $Name

    if (Test-Path $dst -PathType Leaf) {
        Remove-Item $dst -Force
        Write-Success "$Name uninstalled"
        Write-LogOperation -Action "remove" -Src "" -Dst $dst -Success $true
        return $true
    } elseif (Test-Path $dst -PathType Container) {
        Write-Warning2 "$Name is a directory, skipping (please delete manually)"
        return $false
    } else {
        Write-Info "$Name not installed"
        return $true
    }
}

function Get-AdapterInstalledSkills {
    <#
    .SYNOPSIS
    列出已安装的技能
    #>
    if (-not (Test-Path $AdapterTarget)) {
        return @()
    }

    Get-ChildItem $AdapterTarget | Where-Object { $_.LinkType -eq 'SymbolicLink' } | ForEach-Object {
        "$($_.Name) -> $($_.Target)"
    }
}

function Test-AdapterSkillInstalled {
    <#
    .SYNOPSIS
    检查技能是否已安装
    #>
    param([string]$Name)

    $dst = Join-Path $AdapterTarget $Name
    return (Test-Path $dst -PathType Leaf)
}

function Get-AdapterTarget {
    return $AdapterTarget
}
