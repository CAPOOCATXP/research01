#requires -Version 5.1
<#
.SYNOPSIS
  解压 MVTec AD 的分类压缩包（或整包）到统一的数据根，并做结构体检。

.DESCRIPTION
  MVTec 的每个分类包解压后就是 <category>/train|test|ground_truth，所以只要把
  若干 .tar.xz 解到同一个根目录，就能拼出完整布局。本脚本：
    1. 扫描 -Src 下所有 .tar.xz / .tar / .zip；
    2. 逐个解到 -Dest（已存在的同名目录会先确认，不覆盖已有数据）；
    3. 摊平可能多套的一层（如 mvtec_anomaly_detection/bottle/...）；
    4. 调 prepare_mvtec.py 做体检。

.PARAMETER Src
  下载目录，默认 F:\research\data\_download
.PARAMETER Dest
  数据根，默认 F:\research\data\mvtec_ad
.PARAMETER Force
  允许覆盖已解压的类别目录

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\extract_mvtec.ps1
#>
[CmdletBinding()]
param(
    [string]$Src = 'F:\research\data\_download',
    [string]$Dest = 'F:\research\data\mvtec_ad',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if (-not (Test-Path -LiteralPath $Src)) {
    Write-Host "下载目录不存在：$Src" -ForegroundColor Red
    Write-Host "请先建好并把 .tar.xz 放进去（例如 bottle.tar.xz / tile.tar.xz / screw.tar.xz）。"
    exit 2
}
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

$archives = Get-ChildItem -LiteralPath $Src -File | Where-Object { $_.Name -match '\.(tar\.xz|tar|zip)$' }
if (-not $archives) {
    Write-Host "在 $Src 里没找到 .tar.xz / .tar / .zip" -ForegroundColor Red
    exit 2
}

Write-Host ("找到 {0} 个压缩包，解到 {1}" -f $archives.Count, $Dest) -ForegroundColor Cyan

foreach ($a in $archives) {
    $name = $a.Name
    $base = $name -replace '\.(tar\.xz|tar|zip)$', ''
    $target = Join-Path $Dest $base
    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        Write-Host ("[skip] {0}（{1} 已存在；加 -Force 可重解）" -f $name, $base) -ForegroundColor DarkGray
        continue
    }
    Write-Host ("[extract] {0}  ({1:N1} MB)" -f $name, ($a.Length / 1MB))
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if ($name -match '\.zip$') {
        Expand-Archive -LiteralPath $a.FullName -DestinationPath $Dest -Force
    } else {
        & tar -xf $a.FullName -C $Dest
        if ($LASTEXITCODE -ne 0) { throw "tar 解压失败：$name（退出码 $LASTEXITCODE）" }
    }
    Write-Host ("        {0:N1}s" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
}

# 摊平多套的一层目录（例如 mvtec_anomaly_detection/bottle）
$known = @('bottle','cable','capsule','carpet','grid','hazelnut','leather','metal_nut',
           'pill','screw','tile','toothbrush','transistor','wood','zipper')
foreach ($d in (Get-ChildItem -LiteralPath $Dest -Directory)) {
    $hasCat = (Get-ChildItem -LiteralPath $d.FullName -Directory | Where-Object { $known -contains $_.Name }).Count
    if ($hasCat -gt 0 -and -not ($known -contains $d.Name)) {
        Write-Host ("[flatten] {0}/ -> 上层" -f $d.Name) -ForegroundColor Yellow
        foreach ($inner in (Get-ChildItem -LiteralPath $d.FullName -Directory)) {
            $dst = Join-Path $Dest $inner.Name
            if (Test-Path -LiteralPath $dst) {
                Get-ChildItem -LiteralPath $inner.FullName -Force | Move-Item -Destination $dst -Force
                Remove-Item -LiteralPath $inner.FullName -Recurse -Force
            } else {
                Move-Item -LiteralPath $inner.FullName -Destination $dst
            }
        }
        if (-not (Get-ChildItem -LiteralPath $d.FullName -Force)) { Remove-Item -LiteralPath $d.FullName -Force }
    }
}

Write-Host "`n--- 结构体检 ---" -ForegroundColor Cyan
$py = 'C:\Users\yuantai\.conda\envs\adedge-patchcore\python.exe'
& $py (Join-Path $PSScriptRoot 'prepare_mvtec.py') --root $Dest
exit $LASTEXITCODE
