#requires -Version 5.1
<#
.SYNOPSIS
  Fetch official baseline repositories as ZIP snapshots pinned to exact commit SHAs,
  plus the official MVTec AD evaluation code. Write an anchor report.

.DESCRIPTION
  Why not `git clone`? On this machine `git ls-remote` works but `git clone` stalls
  (tested with and without HTTP/1.1, --depth 1, credential helpers disabled).
  Downloading the codeload ZIP over .NET/schannel completes normally, so we pin the
  exact commit SHA inside the URL instead of trusting a branch name.

  Anchor fields recorded per source:
    source URL, commit SHA, upstream commit date, download time, archive size,
    archive sha256, extracted file count, extracted bytes, extracted tree fingerprint
    (sha256 over the sorted "relpath|sha256" listing).

  The tree fingerprint is the comparable anchor: re-fetch and compare. If it changes,
  the tree you are using is not the commit you pinned.

.PARAMETER Root
  Project root. Default F:\research

.PARAMETER Force
  Re-download and re-extract even when files already exist.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch_sources.ps1
#>
[CmdletBinding()]
param(
    [string]$Root = 'F:\research',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-TreeFingerprint {
    param([string]$Dir)
    $files = Get-ChildItem -LiteralPath $Dir -Recurse -File | Sort-Object FullName
    $lines = foreach ($f in $files) {
        $rel = $f.FullName.Substring($Dir.Length).TrimStart('\')
        $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        "$rel|$h"
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
    $fp = ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join ''
    [pscustomobject]@{
        file_count  = @($files).Count
        total_bytes = (@($files) | Measure-Object -Property Length -Sum).Sum
        fingerprint = $fp
    }
}

# ---------------------------------------------------------------- target list
$sources = @(
    [pscustomobject]@{
        kind = 'repo'; name = 'patchcore-inspection'
        url = 'https://github.com/amazon-science/patchcore-inspection'
        sha = 'fcaa92f124fb1ad74a7acf56726decd4b27cbcad'
        upstream_date = '2023-03-06'
        note = 'R1 official PatchCore (baseline)'
    },
    [pscustomobject]@{
        kind = 'repo'; name = 'AnomalyDINO'
        url = 'https://github.com/dammsi/AnomalyDINO'
        sha = 'b9d1c2648e3a5247437d4d953d907a8f3d994457'
        upstream_date = '2025-12-17'
        note = 'R2 official AnomalyDINO (baseline)'
    },
    [pscustomobject]@{
        kind = 'tarball'; name = 'mvtec_ad_evaluation'
        url = 'https://www.mydrive.ch/shares/150450/bb24b914a28ddd2b5e35bd53d23177cd/download/439517473-1665675012/mvtec_ad_evaluation.tar.xz'
        sha = $null; upstream_date = '2022-10-13'
        note = 'Official MVTec AD evaluation code (public direct link, no form)'
    }
)

$reposDir = Join-Path $Root 'repos'
$srcDir   = Join-Path $Root 'archive\sources'
$tmpDir   = Join-Path $Root 'tmp'
foreach ($d in @($reposDir, $srcDir, $tmpDir, (Join-Path $Root 'logs'))) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

$results = New-Object System.Collections.Generic.List[object]
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

foreach ($s in $sources) {
    Write-Host "`n=== $($s.name) ===" -ForegroundColor Cyan
    $isTarball = ($s.kind -eq 'tarball')
    $ext = if ($isTarball) { '.tar.xz' } else { '.zip' }
    $archiveName = if ($s.sha) { "$($s.name)-$($s.sha.Substring(0,10))$ext" } else { "$($s.name)$ext" }
    $archivePath = Join-Path $srcDir $archiveName
    $destDir     = if ($isTarball) { Join-Path $srcDir ($s.name + '_extracted') } else { Join-Path $reposDir $s.name }

    # 1) archive: download when missing (must exist even if the extracted dir is present,
    #    otherwise the archive hash cannot be recorded)
    if ((Test-Path -LiteralPath $archivePath) -and -not $Force) {
        Write-Host "[skip] archive exists: $archivePath" -ForegroundColor DarkGray
    } else {
        $dlUrl = if ($isTarball) { $s.url }
                 else { "https://codeload.github.com/" + ($s.url -replace '^https://github\.com/', '') + "/zip/$($s.sha)" }
        Write-Host "[dl  ] $dlUrl"
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        Invoke-WebRequest -Uri $dlUrl -OutFile $archivePath -UseBasicParsing -TimeoutSec 600
        Write-Host ("[dl  ] {0:N0} bytes in {1:N1}s" -f (Get-Item $archivePath).Length, $sw.Elapsed.TotalSeconds) -ForegroundColor Green
    }

    # 2) extract
    if ((Test-Path -LiteralPath $destDir) -and -not $Force) {
        Write-Host "[skip] extracted dir exists: $destDir" -ForegroundColor DarkGray
    } else {
        if (Test-Path -LiteralPath $destDir) { Remove-Item -LiteralPath $destDir -Recurse -Force }
        if ($isTarball) {
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
            & tar -xf $archivePath -C $destDir
            if ($LASTEXITCODE -ne 0) { Write-Warning "tar failed (exit $LASTEXITCODE)" }
        } else {
            $stage = Join-Path $tmpDir ("unzip_" + $s.name)
            if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
            Expand-Archive -LiteralPath $archivePath -DestinationPath $stage -Force
            $inner = Get-ChildItem -LiteralPath $stage -Directory | Select-Object -First 1
            Move-Item -LiteralPath $inner.FullName -Destination $destDir
            Remove-Item -LiteralPath $stage -Recurse -Force
        }
        Write-Host "[unz ] -> $destDir" -ForegroundColor Green
    }

    # 3) fingerprint + record
    $fp = Get-TreeFingerprint -Dir $destDir
    $results.Add([pscustomobject]@{
        name = $s.name; kind = $s.kind; source_url = $s.url; commit_sha = $s.sha
        upstream_date = $s.upstream_date; downloaded_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')
        archive = $archivePath; archive_bytes = (Get-Item $archivePath).Length
        archive_sha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
        extracted_dir = $destDir; file_count = $fp.file_count; total_bytes = $fp.total_bytes
        tree_fingerprint = $fp.fingerprint; note = $s.note
    })
    Write-Host ("[ok  ] files={0}  bytes={1:N0}  fp={2}" -f $fp.file_count, $fp.total_bytes, $fp.fingerprint) -ForegroundColor Green
}

# ---------------------------------------------------------------- key file checks
$checks = @(
    @{ path = "$reposDir\patchcore-inspection\requirements.txt";     label = 'PatchCore requirements.txt' },
    @{ path = "$reposDir\patchcore-inspection\bin\run_patchcore.py"; label = 'PatchCore bin/run_patchcore.py' },
    @{ path = "$reposDir\AnomalyDINO\run_anomalydino.py";            label = 'AnomalyDINO run_anomalydino.py' },
    @{ path = "$reposDir\AnomalyDINO\src\detection.py";              label = 'AnomalyDINO src/detection.py' }
)
Write-Host "`n=== key file checks ===" -ForegroundColor Cyan
$checkRows = foreach ($c in $checks) {
    $ok = Test-Path -LiteralPath $c.path
    Write-Host ("[{0}] {1}" -f $(if ($ok) { 'ok ' } else { 'MISS' }), $c.label)
    [pscustomobject]@{ label = $c.label; path = $c.path; exists = $ok }
}

# ---------------------------------------------------------------- reports
$anchor = [pscustomobject]@{
    generated_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')
    host = $env:COMPUTERNAME
    root = $Root
    method = 'codeload ZIP pinned to commit SHA (git clone stalls on this machine)'
    sources = $results
    key_file_checks = $checkRows
}
$jsonPath = Join-Path $Root 'logs\anchors_latest.json'
$mdPath   = Join-Path $Root ('logs\anchors_' + $stamp + '.md')
Write-Utf8NoBom -Path $jsonPath -Text ($anchor | ConvertTo-Json -Depth 6)

$md = New-Object System.Text.StringBuilder
[void]$md.AppendLine('# Anchor report (anchors)')
[void]$md.AppendLine('')
[void]$md.AppendLine("- generated_at: $($anchor.generated_at)")
[void]$md.AppendLine("- host: $($anchor.host)   root: $Root")
[void]$md.AppendLine("- method: $($anchor.method)")
[void]$md.AppendLine('')
[void]$md.AppendLine('| name | kind | commit / source | upstream date | archive sha256 | files | bytes | tree fingerprint |')
[void]$md.AppendLine('|---|---|---|---|---|---|---|---|')
foreach ($r in $results) {
    $id = if ($r.commit_sha) { '`' + $r.commit_sha + '`' } else { 'official eval code' }
    [void]$md.AppendLine("| $($r.name) | $($r.kind) | $id | $($r.upstream_date) | ``$($r.archive_sha256)`` | $($r.file_count) | $($r.total_bytes) | ``$($r.tree_fingerprint)`` |")
}
[void]$md.AppendLine('')
[void]$md.AppendLine('## key file checks')
[void]$md.AppendLine('')
foreach ($c in $checkRows) { [void]$md.AppendLine("- [$(if ($c.exists) { 'x' } else { ' ' })] $($c.label)") }
[void]$md.AppendLine('')
[void]$md.AppendLine('## rules')
[void]$md.AppendLine('')
[void]$md.AppendLine('- `repos\` is read-only. To patch code, export a diff: `git diff --no-index original modified > project\patches\xxx.patch`.')
[void]$md.AppendLine('- Whenever sources are re-fetched, compare `tree_fingerprint`; a mismatch means you are not using the commit you pinned.')
Write-Utf8NoBom -Path $mdPath -Text $md.ToString()

Write-Host "`nreport: $mdPath" -ForegroundColor Green
Write-Host "json  : $jsonPath" -ForegroundColor Green
$results | Format-Table name, commit_sha, file_count, archive_sha256 -AutoSize
