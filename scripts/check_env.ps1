#requires -Version 5.1
<#
.SYNOPSIS
    Day 1 第 2 件事：验证一个 conda 环境是否真的可用于本项目（环境隔离的验收脚本）。

.DESCRIPTION
    做四件事，全部留档到 <Root>\logs\：
      1. 记录解释器、torch/torchvision、CUDA 运行时版本；
      2. **真跑一次 GPU 前向+反向**（不是只看 torch.cuda.is_available()），
         用来抓 sm_89 (RTX 4070 Laptop) 上的 "no kernel image is available" —— 老 CUDA wheel 的典型症状；
      3. 用 wide_resnet50_2（weights=None，不需下载权重）实测 256/384/512 分辨率下的 batch 上限与峰值显存；
      4. 导出 pip freeze 与 pip check，写成 env_<环境名>.json / .txt。

    实现说明：探测代码先写到 <Root>\tmp\check_env_probe.py 再执行，
    避免用 python -c 传参时 PowerShell 剥掉引号（会导致 Python 语法错误）。

.PARAMETER EnvName
    conda 环境名，例如 adedge-patchcore。

.PARAMETER Python
    直接指定解释器绝对路径（优先级最高）。不传时按顺序找：
      当前已激活且同名的环境 -> E:\anaconda\envs\<EnvName>\python.exe -> conda run -n <EnvName>
      （Windows PowerShell 5.1 下 conda run 可能失败，优先用绝对路径。）

.PARAMETER Root
    日志输出根目录，默认 G:\adedge。

.EXAMPLE
    .\check_env.ps1 -EnvName adedge-patchcore
.EXAMPLE
    .\check_env.ps1 -Python E:\anaconda\envs\adedge-patchcore\python.exe -Root G:\adedge
#>
[CmdletBinding()]
param(
    [string]$EnvName = 'adedge-patchcore',
    [string]$Python = '',
    [string]$Root = 'G:\adedge'
)

$ErrorActionPreference = 'Stop'

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

# ---------------------------------------------------------------- 定位解释器
$candidates = @()
if ($Python) { $candidates += $Python }
if ($env:CONDA_PREFIX -and (Split-Path $env:CONDA_PREFIX -Leaf) -eq $EnvName) {
    $candidates += (Join-Path $env:CONDA_PREFIX 'python.exe')
}
$candidates += (Join-Path 'E:\anaconda\envs' "$EnvName\python.exe")

$py = $null
foreach ($c in $candidates) { if ($c -and (Test-Path -LiteralPath $c)) { $py = $c; break } }

if ($py) {
    $exe = $py
    $prefixArgs = @()
    Write-Host "[env] 使用解释器: $py" -ForegroundColor Green
} else {
    $exe = 'conda'
    $prefixArgs = @('run', '-n', $EnvName, 'python')
    Write-Host "[env] 未找到 $EnvName 的 python.exe，改用 conda run（较慢）" -ForegroundColor Yellow
}

function Invoke-PyFile {
    param([string]$FilePath)
    if ($prefixArgs.Count -gt 0) { & $exe @prefixArgs $FilePath } else { & $exe $FilePath }
}
function Invoke-PyArgs {
    param([string[]]$ArgList)
    if ($prefixArgs.Count -gt 0) { & $exe @prefixArgs @ArgList } else { & $exe @ArgList }
}

# ---------------------------------------------------------------- 探测代码（落盘执行）
$probe = @'
import json, sys, importlib.metadata as md
out = {"env_name": "__ENV__"}
out["python"] = sys.version.split()[0]
out["executable"] = sys.executable

try:
    import torch, torchvision
    out["torch"] = torch.__version__
    out["torchvision"] = torchvision.__version__
    out["torch_cuda"] = torch.version.cuda
    out["cudnn"] = torch.backends.cudnn.version()
    out["cuda_available"] = bool(torch.cuda.is_available())
except Exception as e:
    out["torch_error"] = "%s: %s" % (type(e).__name__, e)

if out.get("cuda_available"):
    try:
        out["device"] = torch.cuda.get_device_name(0)
        out["capability"] = list(torch.cuda.get_device_capability(0))
        out["total_mem_MiB"] = round(torch.cuda.get_device_properties(0).total_memory / 2**20, 1)

        # 1) sm_89 kernel 是否真的存在：前向 + 反向
        try:
            torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
            x = torch.randn(8, 3, 256, 256, device="cuda")
            conv = torch.nn.Conv2d(3, 16, 3, padding=1).to("cuda")
            y = conv(x); y.mean().backward(); torch.cuda.synchronize()
            out["gpu_smoke"] = "OK"
            out["gpu_smoke_peak_MiB"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        except Exception as e:
            out["gpu_smoke"] = "FAIL"
            out["gpu_smoke_error"] = "%s: %s" % (type(e).__name__, e)

        # 2) 真实 backbone 的显存上限（WRN-50 架构，weights=None 不需下载）
        try:
            backbone = torchvision.models.wide_resnet50_2(weights=None).eval().cuda()
            out["probe_backbone"] = "wide_resnet50_2(weights=None)"
        except Exception as e:
            backbone = conv
            out["probe_backbone"] = "Conv2d(3,16,3) fallback: %s" % e

        limits = {}
        for res in (256, 384, 512):
            best = None
            for bs in (16, 8, 4, 2, 1):
                xx = None
                try:
                    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
                    xx = torch.randn(bs, 3, res, res, device="cuda")
                    with torch.no_grad():
                        _ = backbone(xx)
                    torch.cuda.synchronize()
                    best = {"batch": bs, "peak_MiB": round(torch.cuda.max_memory_allocated() / 2**20, 1)}
                    break
                except Exception as e:
                    msg = str(e).lower()
                    if xx is not None:
                        try: del xx
                        except Exception: pass
                    torch.cuda.empty_cache()
                    if "out of memory" in msg:
                        continue
                    best = {"error": "%s: %s" % (type(e).__name__, e)}
                    break
            limits[str(res)] = best if best is not None else {"batch": None, "note": "全部 batch 都 OOM"}
        out["resolution_limit"] = limits
        try: del backbone
        except Exception: pass
        torch.cuda.empty_cache()
    except Exception as e:
        out["cuda_probe_error"] = "%s: %s" % (type(e).__name__, e)

for p in ["numpy", "scipy", "scikit-learn", "faiss-cpu", "opencv-python",
          "pillow", "pandas", "matplotlib", "timm", "anomalib"]:
    try:
        out[p] = md.version(p)
    except Exception:
        out[p] = None

print("ADEDGE_JSON_BEGIN")
print(json.dumps(out, indent=2, ensure_ascii=False))
print("ADEDGE_JSON_END")
'@ -replace '__ENV__', $EnvName

# ---------------------------------------------------------------- 运行探测
$tmpDir = Join-Path $Root 'tmp'
if (-not (Test-Path -LiteralPath $tmpDir)) { New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null }
$probePath = Join-Path $tmpDir 'check_env_probe.py'
Write-Utf8NoBom -Path $probePath -Text $probe

Write-Host "[run] 探测中（首次会编译 kernel，可能数十秒）..." -ForegroundColor Cyan
$raw = (Invoke-PyFile -FilePath $probePath | Out-String)
$s = $raw.IndexOf('ADEDGE_JSON_BEGIN')
$e = $raw.IndexOf('ADEDGE_JSON_END')
if ($s -lt 0 -or $e -lt 0) {
    Write-Host $raw
    throw "未能从解释器取得探测结果。请检查上面的 Python 报错；若 conda run 不可用，请改用 -Python <绝对路径>。"
}
$jsonText = $raw.Substring($s + 'ADEDGE_JSON_BEGIN'.Length, $e - $s - 'ADEDGE_JSON_BEGIN'.Length).Trim()
$info = $jsonText | ConvertFrom-Json

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $Root 'logs'
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

$jsonPath   = Join-Path $logDir "env_$EnvName`_$stamp.json"
$freezePath = Join-Path $logDir "pip_freeze_$EnvName`_$stamp.txt"
$checkPath  = Join-Path $logDir "pip_check_$EnvName`_$stamp.txt"

$freeze = (Invoke-PyArgs -ArgList @('-m', 'pip', 'freeze') | Out-String)
$check  = (Invoke-PyArgs -ArgList @('-m', 'pip', 'check')  | Out-String)

Write-Utf8NoBom -Path $jsonPath   -Text $jsonText
Write-Utf8NoBom -Path $freezePath -Text $freeze
Write-Utf8NoBom -Path $checkPath  -Text $check
$freezeHash = (Get-FileHash -LiteralPath $freezePath -Algorithm SHA256).Hash

# ---------------------------------------------------------------- 汇总
Write-Host "`n=== 环境验收：$EnvName ===" -ForegroundColor Cyan
Write-Host ("python      : {0}  ({1})" -f $info.python, $info.executable)
if ($info.PSObject.Properties.Name -contains 'torch') {
    Write-Host ("torch       : {0}  (cuda runtime {1}, cudnn {2})" -f $info.torch, $info.torch_cuda, $info.cudnn)
    Write-Host ("cuda avail  : {0}" -f $info.cuda_available)
}
if ($info.PSObject.Properties.Name -contains 'torch_error') {
    Write-Host ("torch 不可用 : {0}" -f $info.torch_error) -ForegroundColor Yellow
}
if ($info.PSObject.Properties.Name -contains 'capability') {
    Write-Host ("device      : {0}  sm_{1}{2}  {3} MiB" -f $info.device, $info.capability[0], $info.capability[1], $info.total_mem_MiB)
}
if ($info.PSObject.Properties.Name -contains 'gpu_smoke') {
    $color = if ($info.gpu_smoke -eq 'OK') { 'Green' } else { 'Red' }
    Write-Host ("GPU 冒烟    : {0}  (峰值 {1} MiB)" -f $info.gpu_smoke, $info.gpu_smoke_peak_MiB) -ForegroundColor $color
    if ($info.gpu_smoke -eq 'FAIL') {
        Write-Host "  -> 若错误含 'no kernel image is available'，说明该 torch/CUDA wheel 不支持 sm_89；" -ForegroundColor Red
        Write-Host "     Ada 架构自 CUDA 11.8 起支持，需换 cu118 或更新的 torch 构建。" -ForegroundColor Red
    }
}
if ($info.PSObject.Properties.Name -contains 'resolution_limit') {
    Write-Host ("分辨率上限（backbone = {0}）:" -f $info.probe_backbone)
    $info.resolution_limit.PSObject.Properties | ForEach-Object {
        Write-Host ("  {0}px -> batch {1}  peak {2} MiB" -f $_.Name, $_.Value.batch, $_.Value.peak_MiB)
    }
}
$missing = @()
foreach ($p in @('numpy','scipy','scikit-learn','faiss-cpu','opencv-python','pillow')) {
    if ($info.PSObject.Properties.Name -contains $p -and -not $info.$p) { $missing += $p }
}
if ($missing.Count) { Write-Host ("缺失常用包: {0}" -f ($missing -join ', ')) -ForegroundColor Yellow }

Write-Host "`nJSON      : $jsonPath"
Write-Host "freeze    : $freezePath  (sha256 $freezeHash)"
Write-Host "pip check : $checkPath`n"
Write-Host "把上面这些数字抄进 environment.md 第 2 节；freeze 的 sha256 写进每次运行的 run.json。" -ForegroundColor DarkGray
