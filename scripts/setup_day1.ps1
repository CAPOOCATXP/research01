#requires -Version 5.1
<#
.SYNOPSIS
    Day 1 第 1+3 件事：建立目录骨架 + 锚定仓库（幂等，可反复运行）。

.DESCRIPTION
    - 建立 G:\adedge 下的固定目录约定（已存在则跳过，绝不覆盖已有文件）。
    - 为 project 建立你自己的 git 仓库，并写入 README 骨架（仅在缺失时写入）。
    - 克隆官方仓库（需 -Clone），并记录不可变锚点：
      URL / 默认分支 / HEAD commit / commit 日期 / 工作区是否干净。
    - 对 cache 下所有 .pth/.pt/.bin/.safetensors 计算 sha256。
    - 结果写入 <Root>\logs\anchors_<时间戳>.md 与 anchors_latest.json（UTF-8 无 BOM）。

    官方仓库在 repos\ 下视为只读：任何修补都导出成 project\patches\*.patch，
    不要直接改 repos\ 里的文件（否则 anchors 里的 dirty=1 会让复现失效）。

.PARAMETER Root
    工作根目录，默认 G:\adedge（本机 G: 有 530 GB 空闲）。

.PARAMETER Clone
    缺失时执行 git clone。不加此开关时只做本地锚点扫描。

.PARAMETER SetCacheEnv
    把 TORCH_HOME / HF_HOME / ADEDGE_ROOT 写进用户级环境变量，避免权重落到 C:。

.PARAMETER Repos
    要锚定的仓库 URL 列表。默认两个官方基线仓库；若与导师 handout 附录 R1 链接不同，用本参数覆盖：
      .\setup_day1.ps1 -Root G:\adedge -Clone -Repos 'https://github.com/xxx/patchcore.git'

.EXAMPLE
    # 只建骨架 + 初始化自己的仓库
    .\setup_day1.ps1 -Root G:\adedge

.EXAMPLE
    # 建骨架 + 克隆 + 锚定 + 配置缓存环境变量
    .\setup_day1.ps1 -Root G:\adedge -Clone -SetCacheEnv
#>
[CmdletBinding()]
param(
    [string]$Root = 'G:\adedge',
    [switch]$Clone,
    [switch]$SetCacheEnv,
    [string[]]$Repos = @(
        'https://github.com/amazon-science/patchcore-inspection.git',
        'https://github.com/dammsi/AnomalyDINO.git'
    )
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- 工具函数
$script:Created = New-Object System.Collections.Generic.List[string]
$script:Skipped = New-Object System.Collections.Generic.List[string]

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

function New-DirSafe {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) { $script:Skipped.Add($Path) }
    else { New-Item -ItemType Directory -Force -Path $Path | Out-Null; $script:Created.Add($Path) }
}

function Invoke-Git {
    param([string[]]$GitArgs, [string]$WorkDir)
    # 关键：函数作用域内把 $ErrorActionPreference 降为 Continue（局部生效，自动恢复）。
    # 否则 git 写向 stderr 的正常信息（clone 进度、warning）在 Stop 模式下会变成终止性错误，
    # 脚本会在第一次 clone 时中断。
    $ErrorActionPreference = 'Continue'
    Push-Location -LiteralPath $WorkDir
    try {
        $out = & git @GitArgs 2>&1
        $code = $LASTEXITCODE
        $text = ($out | ForEach-Object { $_.ToString() }) -join "`n"
    } finally { Pop-Location }
    [pscustomobject]@{ Output = $text.Trim(); ExitCode = $code }
}

# ---------------------------------------------------------------- 0. 前置检查
$Root = $Root.TrimEnd('\')
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "找不到 git，请先安装或把 git 加入 PATH。" }

$rootParent = Split-Path $Root -Parent
if (-not (Test-Path -LiteralPath $rootParent)) { throw "父目录不存在：$rootParent（请确认盘符）" }
if ($Root.Length -gt 60) { Write-Warning "根路径较长（$($Root.Length) 字符），Windows 260 字符限制可能触发，建议用短路径。" }

Write-Host "`n=== Day 1 setup | Root = $Root | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Cyan

# ---------------------------------------------------------------- 1. 目录骨架
New-DirSafe $Root
$subDirs = @(
    'repos',                    # 官方仓库（只读）
    'data',                     # 数据集（只读）
    'cache', 'cache\weights', 'cache\features', 'cache\torch', 'cache\hf',
    'manifests',                # reference-fit / development / calibration 清单
    'configs',                  # 运行配置
    'runs',                     # 每次实验的输出
    'logs',                     # 日志 + 锚点报告
    'scripts',                  # 本脚本与检查脚本
    'reports',                  # 周报 / Gate 报告
    'archive',                  # 冻结快照（论文存档）
    'tmp',
    'project', 'project\src', 'project\patches', 'project\configs'
)
foreach ($d in $subDirs) { New-DirSafe (Join-Path $Root $d) }

# ---------------------------------------------------------------- 2. 自己的代码仓库
$projectDir = Join-Path $Root 'project'
if (-not (Test-Path (Join-Path $projectDir '.git'))) {
    $r = Invoke-Git -GitArgs @('init', '-b', 'main') -WorkDir $projectDir
    if ($r.ExitCode -ne 0) { $r = Invoke-Git -GitArgs @('init') -WorkDir $projectDir }   # 老版本 git 回退
    Write-Host "[git] 已初始化自己的仓库: $projectDir (branch=main)" -ForegroundColor Green
} else {
    Write-Host "[git] 自己的仓库已存在: $projectDir（跳过 init）" -ForegroundColor DarkGray
}

$readmePath = Join-Path $projectDir 'README.md'
if (-not (Test-Path $readmePath)) {
    $readme = @"
# adedge — 项目代码仓库

> 一句话目标：检验「正常参考库被压缩后，工业异常报警的二元决策是否仍然一致」，
> 并用保守距离区间做「确定正常 / 确定报警 / 升级查询」的可审计筛查。

## 路径约定（不要随意更改）

| 用途 | 路径 | 读写规则 |
|---|---|---|
| 官方基线仓库 | ``$Root\repos\`` | **只读**。任何修补导出为 ``project\patches\*.patch`` |
| 数据集 | ``$Root\data\`` | **只读**。下载后不再改动 |
| 权重 / 特征缓存 | ``$Root\cache\`` | TORCH_HOME / HF_HOME 指向这里 |
| 角色清单 | ``$Root\manifests\`` | reference-fit / development / calibration，同一原图不跨角色 |
| 运行输出 | ``$Root\runs\<日期>_<实验名>\`` | 每次运行一个目录，含 run.json |
| 日志与锚点 | ``$Root\logs\`` | anchors_*.json / env_*.json |

## 复现一份运行需要什么

``run.json`` 必须记录：env 名 + ``pip freeze`` 哈希、仓库 commit、权重 sha256、
数据清单 sha256、阈值与聚合方式、随机种子、命令原文。

## 本周（W1）不包含

任何模型改进、剪枝/量化/蒸馏、扩散增强、多模态融合。
"@
    Write-Utf8NoBom -Path $readmePath -Text $readme
    Write-Host "[fs ] 写入 README 骨架: $readmePath" -ForegroundColor Green
} else {
    Write-Host "[fs ] README 已存在，不覆盖: $readmePath" -ForegroundColor DarkGray
}

$gitignorePath = Join-Path $projectDir '.gitignore'
if (-not (Test-Path $gitignorePath)) {
    Write-Utf8NoBom -Path $gitignorePath -Text @"
__pycache__/
*.pyc
.ipynb_checkpoints/
*.pth
*.pt
*.onnx
.venv/
"@
    Write-Host "[fs ] 写入 .gitignore: $gitignorePath" -ForegroundColor Green
}

# ---------------------------------------------------------------- 3. 克隆（可选）
$repoAnchors = New-Object System.Collections.Generic.List[object]
foreach ($url in $Repos) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($url)
    $dest = Join-Path (Join-Path $Root 'repos') $name

    if (-not (Test-Path (Join-Path $dest '.git'))) {
        if ($Clone) {
            Write-Host "[git] 克隆 $url -> $dest" -ForegroundColor Yellow
            $r = Invoke-Git -GitArgs @('clone', '--quiet', $url, $dest) -WorkDir (Join-Path $Root 'repos')
            if ($r.ExitCode -ne 0) {
                Write-Warning "克隆失败（$name）：$($r.Output)"
                $repoAnchors.Add([pscustomobject]@{
                    repo = $name; url = $url; commit = $null; branch = $null; commit_date = $null
                    subject = $null; dirty = $null; status = "CLONE_FAILED"
                })
                continue
            }
        } else {
            $repoAnchors.Add([pscustomobject]@{
                repo = $name; url = $url; commit = $null; branch = $null; commit_date = $null
                subject = $null; dirty = $null; status = "NOT_CLONED (加 -Clone 或手动 clone)"
            })
            continue
        }
    }

    $commit = (Invoke-Git -GitArgs @('rev-parse', 'HEAD') -WorkDir $dest).Output
    $cdate  = (Invoke-Git -GitArgs @('log', '-1', '--format=%cI') -WorkDir $dest).Output
    $subj   = (Invoke-Git -GitArgs @('log', '-1', '--format=%s') -WorkDir $dest).Output
    $branch = (Invoke-Git -GitArgs @('rev-parse', '--abbrev-ref', 'HEAD') -WorkDir $dest).Output
    $remote = (Invoke-Git -GitArgs @('remote', 'get-url', 'origin') -WorkDir $dest).Output
    $dirtyRaw = (Invoke-Git -GitArgs @('status', '--porcelain') -WorkDir $dest).Output
    $dirtyFiles = @()
    if ($dirtyRaw) { $dirtyFiles = $dirtyRaw -split "`r?`n" | Where-Object { $_ } }

    $repoAnchors.Add([pscustomobject]@{
        repo = $name; url = $remote; branch = $branch; commit = $commit; commit_date = $cdate
        subject = $subj; dirty = ($dirtyFiles.Count -gt 0); dirty_files = $dirtyFiles.Count
        status = if ($dirtyFiles.Count -gt 0) { 'DIRTY' } else { 'CLEAN' }
    })
    $color = if ($dirtyFiles.Count -gt 0) { 'Yellow' } else { 'Green' }
    Write-Host ("[git] {0,-24} {1}  {2}" -f $name, $commit.Substring(0, [Math]::Min(10, $commit.Length)), $cdate) -ForegroundColor $color
}

# ---------------------------------------------------------------- 4. 权重指纹
$exts = @('.pth', '.pt', '.bin', '.safetensors', '.ckpt')
$weightFiles = @()
$cacheDir = Join-Path $Root 'cache'
if (Test-Path $cacheDir) {
    $weightFiles = Get-ChildItem -LiteralPath $cacheDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $exts -contains $_.Extension.ToLower() }
}
$weights = foreach ($f in $weightFiles) {
    [pscustomobject]@{
        file = $f.FullName; size_MB = [Math]::Round($f.Length / 1MB, 1)
        sha256 = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        mtime = $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
    }
}
if ($weightFiles.Count -eq 0) { Write-Host "[wgt] cache\ 下暂无权重文件（下载后用同一命令重跑即可）" -ForegroundColor DarkGray }
else { Write-Host "[wgt] 已指纹 $($weightFiles.Count) 个权重文件" -ForegroundColor Green }

# ---------------------------------------------------------------- 5. 输出锚点报告
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $Root 'logs'
$mdPath = Join-Path $logDir "anchors_$stamp.md"
$jsPath = Join-Path $logDir 'anchors_latest.json'

$anchorObj = [pscustomobject]@{
    generated_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')
    host         = $env:COMPUTERNAME
    root         = $Root
    repos        = $repoAnchors
    weights      = @($weights)
}

$md = New-Object System.Text.StringBuilder
[void]$md.AppendLine("# 仓库锚定报告 (anchors)")
[void]$md.AppendLine("")
[void]$md.AppendLine("- 生成时间：$($anchorObj.generated_at)")
[void]$md.AppendLine("- 主机：$($anchorObj.host)　根目录：``$Root``")
[void]$md.AppendLine("")
[void]$md.AppendLine("## 1. 仓库")
[void]$md.AppendLine("")
[void]$md.AppendLine("| 仓库 | 分支 | HEAD commit | commit 日期 | 工作区 | 最近提交 |")
[void]$md.AppendLine("|---|---|---|---|---|---|")
foreach ($r in $repoAnchors) {
    $c = if ($r.commit) { $r.commit } else { '—' }
    $cd = if ($r.commit_date) { $r.commit_date } else { '—' }
    $st = if ($null -eq $r.dirty) { $r.status } elseif ($r.dirty) { "DIRTY ($($r.dirty_files) 个文件被改)" } else { 'CLEAN ✅' }
    [void]$md.AppendLine("| $($r.repo) | $($r.branch) | ``$c`` | $cd | $st | $($r.subject) |")
}
[void]$md.AppendLine("")
[void]$md.AppendLine("## 2. 权重指纹 (sha256)")
[void]$md.AppendLine("")
if ($weights.Count -eq 0) {
    [void]$md.AppendLine("_cache\ 下暂无权重文件。下载权重后重跑本脚本即可填充。_")
} else {
    [void]$md.AppendLine("| 文件 | 大小 MB | sha256 | 修改时间 |")
    [void]$md.AppendLine("|---|---|---|---|")
    foreach ($w in $weights) { [void]$md.AppendLine("| ``$($w.file)`` | $($w.size_MB) | ``$($w.sha256)`` | $($w.mtime) |") }
}
[void]$md.AppendLine("")
[void]$md.AppendLine("## 3. 目录骨架")
[void]$md.AppendLine("")
[void]$md.AppendLine("本次新建 $($script:Created.Count) 个路径，已存在 $($script:Skipped.Count) 个（幂等重跑不会报错）。")
[void]$md.AppendLine("")
[void]$md.AppendLine("> 纪律：``repos\`` 只读；要改代码就导出 ``project\patches\*.patch``。")
[void]$md.AppendLine("> 锚定后**不要** ``git pull``；升级 = 新目录 + 重新锚定。")

Write-Utf8NoBom -Path $mdPath -Text $md.ToString()
Write-Utf8NoBom -Path $jsPath -Text ($anchorObj | ConvertTo-Json -Depth 6)

if ($SetCacheEnv) {
    [Environment]::SetEnvironmentVariable('ADEDGE_ROOT', $Root, 'User')
    [Environment]::SetEnvironmentVariable('TORCH_HOME', (Join-Path $Root 'cache\torch'), 'User')
    [Environment]::SetEnvironmentVariable('HF_HOME',    (Join-Path $Root 'cache\hf'),    'User')
    [Environment]::SetEnvironmentVariable('HF_HUB_CACHE', (Join-Path $Root 'cache\hf\hub'), 'User')
    Write-Host "[env] 已写入用户级环境变量 ADEDGE_ROOT / TORCH_HOME / HF_HOME / HF_HUB_CACHE" -ForegroundColor Green
    Write-Host "      新开一个终端才会生效。" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------- 6. 汇总
Write-Host "`n--- 仓库锚点 ---" -ForegroundColor Cyan
$repoAnchors | Format-Table repo, commit, commit_date, status -AutoSize
Write-Host "报告：$mdPath"
Write-Host "JSON：$jsPath"
Write-Host "目录骨架：新建 $($script:Created.Count) / 已存在 $($script:Skipped.Count)`n"

$dirtyRepos = @($repoAnchors | Where-Object { $_.dirty -eq $true })
if ($dirtyRepos.Count -gt 0) {
    Write-Warning "有仓库工作区不干净，锚点无效：$($dirtyRepos.repo -join ', ')。恢复：git -C <repo> checkout -- ."
}
