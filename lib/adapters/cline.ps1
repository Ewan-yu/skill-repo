# cline.ps1 - Cline 适配器 (PowerShell)
# 安装方式：复制 SKILL.md 内容作为规则文件

$AdapterTarget = Join-Path $env:USERPROFILE ".cline\rules"
$AdapterName = "cline"

function Install-AdapterSkill {
    param(
        [string]$Src,
        [string]$Name
    )

    $dst = Join-Path $AdapterTarget "$Name.md"
    $skillFile = Join-Path $Src "SKILL.md"

    if (-not (Test-Path $skillFile)) {
        Write-Error2 "$Name: SKILL.md not found"
        return $false
    }

    if (-not (Test-Path $AdapterTarget)) {
        New-Item -ItemType Directory -Path $AdapterTarget -Force | Out-Null
    }

    if (Test-Path $dst) {
        Write-Warning2 "$Name already exists in $AdapterTarget"
        if (Confirm-Action "Overwrite?") {
            Remove-Item $dst -Force
        } else {
            return $false
        }
    }

    $content = Get-Content $skillFile -Raw
    $body = ""
    if ($content -match '(?s)^---\r?\n.*?\r?\n---\r?\n(.*)') {
        $body = $Matches[1]
    }

    $meta = Parse-SkillMeta -SkillDir $Src
    $version = if ($meta.version) { $meta.version } else { "unknown" }

    $header = "<!-- Skill: $Name v$version -->`n<!-- Agent: cline -->`n`n"
    Set-Content -Path $dst -Value ($header + $body)

    Write-Success "$Name -> $dst"
    Write-LogOperation -Action "copy" -Src $skillFile -Dst $dst -Success $true
    Push-Rollback "Remove-Item '$dst' -Force"
    return $true
}

function Uninstall-AdapterSkill {
    param([string]$Name)

    $dst = Join-Path $AdapterTarget "$Name.md"

    if (Test-Path $dst) {
        Remove-Item $dst -Force
        Write-Success "$Name uninstalled from Cline"
        Write-LogOperation -Action "remove" -Src "" -Dst $dst -Success $true
        return $true
    } else {
        Write-Info "$Name not installed in Cline"
        return $true
    }
}

function Get-AdapterInstalledSkills {
    if (-not (Test-Path $AdapterTarget)) {
        return @()
    }

    Get-ChildItem $AdapterTarget -Filter "*.md" | Where-Object {
        (Get-Content $_.FullName -First 1) -match '<!-- Skill:'
    } | ForEach-Object {
        $_.BaseName
    }
}

function Test-AdapterSkillInstalled {
    param([string]$Name)

    $dst = Join-Path $AdapterTarget "$Name.md"
    if (Test-Path $dst) {
        return ((Get-Content $dst -First 1) -match '<!-- Skill:')
    }
    return $false
}

function Get-AdapterTarget {
    return $AdapterTarget
}
