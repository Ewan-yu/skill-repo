# install.ps1 - 创建符号链接将技能安装到 Claude Code
$ErrorActionPreference = "Stop"

$skillRepo = Join-Path $PSScriptRoot "skills"
$claudeSkills = Join-Path $env:USERPROFILE ".claude\skills"

# 技能列表
$skills = @("cn-stock-analysis", "mx-data", "mx-moni", "mx-search",
            "mx-xuangu", "mx-zixuan", "stock-valuation", "wxcj")

Write-Host "安装技能..."
Write-Host "源目录: $skillRepo"
Write-Host "目标目录: $claudeSkills"
Write-Host ""

foreach ($skill in $skills) {
    $src = Join-Path $skillRepo $skill
    $dst = Join-Path $claudeSkills $skill

    if (-not (Test-Path $src)) {
        Write-Host "  警告: 源目录不存在: $src (跳过 $skill)" -ForegroundColor Yellow
        continue
    }

    if (Test-Path $dst -PathType Leaf) {  # Symlink
        Write-Host "  已存在（符号链接）: $skill"
    } elseif (Test-Path $dst -PathType Container) {
        Write-Host "  已存在（目录）: $skill -- 需手动迁移" -ForegroundColor Yellow
        Write-Host "    迁移命令: Remove-Item -Recurse -Force '$dst'; New-Item -ItemType SymbolicLink -Path '$dst' -Target '$src'"
    } else {
        New-Item -ItemType SymbolicLink -Path $dst -Target $src
        Write-Host "  已安装: $skill" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "完成。重启 Claude Code 生效。"
