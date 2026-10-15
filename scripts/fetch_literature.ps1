#requires -Version 5.1
<#
.SYNOPSIS
  Download the A5 reading list (and the R8-R11 papers cited in the plan) from their
  official open-access sources, then record provenance.

.DESCRIPTION
  Design rules (same discipline as fetch_sources.ps1):
    * Prefer the publisher's own open-access version (CVF Open Access, PMLR, arXiv,
      Springer OA). Never use pirate mirrors.
    * Record, per paper: citation, official landing page, the URL actually used,
      retrieval time, byte size, sha256, and a page count as a cheap identity check.
    * PDFs stay OUT of git (see .gitignore): we commit the manifest, not the
      publishers' files. Re-running this script restores them.

  Two traps found on this machine, both handled below:
    1. MDPI returns HTTP 403 to scripted downloads even with a browser User-Agent.
       -> R9 needs a manual browser download; the script reports it as PENDING.
    2. Springer's /content/pdf/... link returns an HTML cookie wall unless you send a
       Referer and keep a cookie jar. -> use curl.exe with -c/-b/-e for that one.

.PARAMETER Root
  Project root. Default F:\research
#>
[CmdletBinding()]
param([string]$Root = 'F:\research')

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$pdfDir = Join-Path $Root 'literature\pdf'
$logDir = Join-Path $Root 'logs'
$tmpDir = Join-Path $Root 'tmp'
foreach ($d in @($pdfDir, $logDir, $tmpDir)) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

$UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

function Test-IsPdf {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $b = [System.IO.File]::ReadAllBytes($Path)
    if ($b.Length -lt 5) { return $false }
    return ([System.Text.Encoding]::ASCII.GetString($b[0..4]) -match '%PDF')
}

function Save-Pdf {
    param([string]$File, [string[]]$Urls, [string]$Referer = '')
    $out = Join-Path $pdfDir $File
    if ((Test-IsPdf $out) -and -not $Force) {
        Write-Host ("[skip] {0}" -f $File) -ForegroundColor DarkGray
        return $true
    }
    foreach ($u in $Urls) {
        try {
            if ($u -match 'link\.springer\.com') {
                # 需要 cookie 会话 + Referer，Invoke-WebRequest 会拿到 HTML 墙
                $ck = Join-Path $tmpDir 'springer.ck'
                & curl.exe -sSL --max-time 180 -c $ck -b $ck -A $UA `
                    -H 'Accept: application/pdf,text/html;q=0.9,*/*;q=0.8' `
                    -e $Referer -o $out $u 2>$null
            } else {
                $hdr = @{ 'Accept' = 'application/pdf,text/html;q=0.9,*/*;q=0.8' }
                if ($Referer) { $hdr['Referer'] = $Referer }
                Invoke-WebRequest -Uri $u -OutFile $out -UserAgent $UA -Headers $hdr `
                    -TimeoutSec 180 -UseBasicParsing
            }
            if (Test-IsPdf $out) {
                Write-Host ("[ok  ] {0,-52} {1,10:N0} B  <- {2}" -f `
                    $File, (Get-Item $out).Length, $u.Substring(0, [Math]::Min(64, $u.Length))) -ForegroundColor Green
                return $true
            }
            Write-Host ("[html] {0,-52} 返回的不是 PDF  <- {1}" -f $File, $u) -ForegroundColor Yellow
        } catch {
            Write-Host ("[fail] {0,-52} {1}" -f $File, $_.Exception.Message) -ForegroundColor Red
        }
        Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
    }
    Write-Host ("[MISS] {0,-52} 全部通道失败" -f $File) -ForegroundColor Red
    return $false
}

# ------------------------------------------------------------------ 清单
# ref, file, 主用 URL, 备用 URL（按顺序尝试）
$items = @(
    @{ ref='R7';  file='R7_cover_trees_ICML2006.pdf';
       urls=@('https://hunch.net/~jl/projects/cover_tree/paper/paper.pdf') },
    @{ ref='R1';  file='R1_patchcore_CVPR2022.pdf';
       urls=@('https://openaccess.thecvf.com/content/CVPR2022/papers/Roth_Towards_Total_Recall_in_Industrial_Anomaly_Detection_CVPR_2022_paper.pdf') },
    @{ ref='R2';  file='R2_anomalydino_WACV2025.pdf';
       urls=@('https://openaccess.thecvf.com/content/WACV2025/papers/Damm_AnomalyDINO_Boosting_Patch-Based_Few-Shot_Anomaly_Detection_with_DINOv2_WACV_2025_paper.pdf') },
    @{ ref='R3';  file='R3_efficientad_WACV2024.pdf';
       urls=@('https://openaccess.thecvf.com/content/WACV2024/papers/Batzner_EfficientAD_Accurate_Visual_Anomaly_Detection_at_Millisecond-Level_Latencies_WACV_2024_paper.pdf',
              'https://www.mvtec.com/fileadmin/Redaktion/mvtec.com/company/research/Batzner_accurate_visual_anomaly_detection_at_millisecond_level_latencies_2024.pdf') },
    @{ ref='R4';  file='R4_mvtec_ad2_IJCV2026.pdf';
       urls=@('https://link.springer.com/content/pdf/10.1007/s11263-026-02743-0.pdf');
       referer='https://link.springer.com/article/10.1007/s11263-026-02743-0' },
    @{ ref='R6';  file='R6_sparc_arXiv2608.18585.pdf';
       urls=@('https://arxiv.org/pdf/2608.18585') },
    @{ ref='R8';  file='R8_calibration_preserving_pruning_arXiv2608.23744.pdf';
       urls=@('https://arxiv.org/pdf/2608.23744') },
    @{ ref='R9';  file='R9_memory_pollution_MDPI2026.pdf';
       urls=@('https://www.mdpi.com/2504-4990/8/7/219/pdf');
       note='MDPI 对脚本下载一律返回 403，需人工用浏览器另存' },
    @{ ref='R10'; file='R10_elkin_kurlin_compressed_cover_tree_ICML2023.pdf';
       urls=@('https://proceedings.mlr.press/v202/elkin23a/elkin23a.pdf') },
    @{ ref='R11'; file='R11_fastref_CVPR2026.pdf';
       urls=@('https://openaccess.thecvf.com/content/CVPR2026/papers/Li_FastRef_Fast_Prototype_Refinement_for_Few-shot_Industrial_Anomaly_Detection_CVPR_2026_paper.pdf',
              'https://arxiv.org/pdf/2506.21398') }
)

Write-Host ("`n=== 下载 A5 阅读清单（{0} 项）-> {1} ===" -f $items.Count, $pdfDir) -ForegroundColor Cyan
$ok = 0
foreach ($it in $items) {
    $ref_ = if ($it.ContainsKey('referer')) { $it['referer'] } else { '' }
    if (Save-Pdf -File $it.file -Urls $it.urls -Referer $ref_) { $ok++ }
}
Write-Host ("`n成功 {0}/{1}" -f $ok, $items.Count) -ForegroundColor Cyan

# ------------------------------------------------------------------ 逐文件留证
$rows = foreach ($f in (Get-ChildItem -LiteralPath $pdfDir -File -Filter *.pdf | Sort-Object Name)) {
    $b = [System.IO.File]::ReadAllBytes($f.FullName)
    $raw = [System.Text.Encoding]::GetEncoding(28591).GetString($b)
    [pscustomobject]@{
        file        = $f.Name
        bytes       = $f.Length
        sha256      = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        pages       = ([regex]::Matches($raw, '/Type\s*/Page[^s]')).Count
        pdf_version = $raw.Substring(0, 8).Trim()
        title_meta  = if ($raw -match '/Title\s*\(([^)]{3,120})\)') { $Matches[1] } else { '' }
    }
}
$json = Join-Path $logDir 'literature_files.json'
[System.IO.File]::WriteAllText($json, ($rows | ConvertTo-Json -Depth 4),
    (New-Object System.Text.UTF8Encoding($false)))
Write-Host ("`n逐文件留证 -> {0}" -f $json) -ForegroundColor Green
$rows | Format-Table file, pages, @{n='MB';e={[math]::Round($_.bytes/1MB,2)}}, @{n='sha256';e={$_.sha256.Substring(0,16)}} -AutoSize
