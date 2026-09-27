param(
  [string]$DataDir = "$env:LOCALAPPDATA\BetterSaul",
  [string]$AppDir = ""
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch { }

if (-not $AppDir) {
  $AppDir = Split-Path -Parent $PSScriptRoot
  if (-not (Test-Path (Join-Path $AppDir "BetterSaul.exe"))) {
    $AppDir = $PSScriptRoot
  }
}

function Say([string]$m) {
  Write-Output $m
}

function Stage([int]$n, [string]$code) {
  Write-Output ("STAGE:{0}|{1}" -f $n, $code)
}

function Pct([int]$n) {
  Write-Output ("PCT:{0}" -f $n)
}

function PctBytes([int]$n, [int64]$got, [int64]$total) {
  Write-Output ("PCT:{0}|{1}|{2}" -f $n, $got, $total)
}

$runtime = Join-Path $DataDir "runtime"
$desktopFolder = Join-Path ([Environment]::GetFolderPath("Desktop")) "BetterSaul"
New-Item -ItemType Directory -Force -Path $runtime, $desktopFolder | Out-Null

function Open-Part([string]$Path, [bool]$Append) {
  $mode = [System.IO.FileMode]::Create
  if ($Append) { $mode = [System.IO.FileMode]::Append }
  $i = 0
  while ($i -lt 10) {
    $i = $i + 1
    try {
      return [System.IO.File]::Open($Path, $mode, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
    } catch {
      Start-Sleep -Seconds $i
    }
  }
  return $null
}

function Get-FileOnce([string]$Url, [string]$OutFile, [string]$Tmp, [int]$From, [int]$To) {
  $have = [int64]0
  if (Test-Path -LiteralPath $Tmp) {
    $have = [int64](Get-Item -LiteralPath $Tmp).Length
  }

  $req = [System.Net.HttpWebRequest]::Create($Url)
  $req.UserAgent = "BetterSaulDesktop/1.3"
  $req.AllowAutoRedirect = $true
  $req.Timeout = 600000
  $req.ReadWriteTimeout = 600000
  if ($have -gt 0) {
    [void]$req.AddRange($have)
  }

  $res = $null
  try {
    $res = $req.GetResponse()
  } catch [System.Net.WebException] {
    $resp = $_.Exception.Response
    if ($resp -and ([int]$resp.StatusCode -eq 416)) {
      Remove-Item -LiteralPath $Tmp -Force -ErrorAction SilentlyContinue
    }
    throw
  }

  $fs = $null
  $src = $null
  try {
    $partial = $false
    if ([int]$res.StatusCode -eq 206) { $partial = $true }
    $chunk = [int64]$res.ContentLength
    $total = [int64]0
    if ($partial -and $chunk -gt 0) { $total = $have + $chunk }
    elseif ($chunk -gt 0) { $total = $chunk }
    if (-not $partial) { $have = [int64]0 }

    $src = $res.GetResponseStream()
    $fs = Open-Part $Tmp $partial
    if (-not $fs) { throw "locked" }

    $buf = New-Object byte[] 262144
    $read = $have
    $last = -1
    while (($n = $src.Read($buf, 0, $buf.Length)) -gt 0) {
      $fs.Write($buf, 0, $n)
      $read = $read + $n
      if ($total -gt 0) {
        $p = [int]($From + (($To - $From) * $read / $total))
        if ($p -ne $last) {
          $last = $p
          PctBytes $p $read $total
        }
      }
    }
  } finally {
    if ($fs) { $fs.Close() }
    if ($src) { $src.Close() }
    if ($res) { $res.Close() }
  }

  $got = [int64]0
  if (Test-Path -LiteralPath $Tmp) { $got = [int64](Get-Item -LiteralPath $Tmp).Length }
  if ($got -le 0) { throw "empty-download" }
  if (Test-Path -LiteralPath $OutFile) {
    Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
  }
  Move-Item -LiteralPath $Tmp -Destination $OutFile -Force
}

function Get-File([string]$Url, [string]$OutFile, [int]$From, [int]$To, [string]$Code) {
  Stage $From $Code
  $dir = Split-Path -Parent $OutFile
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $tmp = "$OutFile.part"
  $tries = 0
  while ($tries -lt 8) {
    $tries = $tries + 1
    try {
      Get-FileOnce $Url $OutFile $tmp $From $To
      Pct $To
      return $true
    } catch {
      Write-Output ("WARN:retry:{0}" -f $tries)
      if ($tries -eq 3) {
        Write-Output "WARN:lock"
        $tmp = "{0}.{1}.part" -f $OutFile, $PID
      }
      Start-Sleep -Seconds (2 * $tries)
    }
  }
  Write-Output ("WARN:skip {0}" -f $Code)
  return $false
}

function Make-Shortcut([string]$lnk, [string]$target, [string]$work) {
  if (-not (Test-Path -LiteralPath $target)) { return }
  try {
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($lnk)
    $s.TargetPath = $target
    $s.WorkingDirectory = $work
    $s.Description = "BetterSaul"
    $s.Save()
  } catch { }
}

Stage 2 "1/7 folders"
$exe = Join-Path $AppDir "BetterSaul.exe"
Make-Shortcut (Join-Path $desktopFolder "BetterSaul.lnk") $exe $AppDir
$readme = @(
  "BetterSaul installed on this PC.",
  "",
  ("Folder: {0}" -f $desktopFolder),
  ("Program: {0}" -f $AppDir),
  ("Data: {0}" -f $DataDir)
) -join "`r`n"
Set-Content -LiteralPath (Join-Path $desktopFolder "Oku.txt") -Value $readme -Encoding ASCII
Pct 6

function Need-WebView2 {
  $keys = @(
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
  )
  foreach ($k in $keys) {
    if (Test-Path $k) { return $false }
  }
  return $true
}

if (Need-WebView2) {
  $wv = Join-Path $runtime "MicrosoftEdgeWebview2Setup.exe"
  if (Get-File "https://go.microsoft.com/fwlink/p/?LinkId=2124703" $wv 6 10 "2/7 webview") {
    Stage 10 "2/7 webview"
    try {
      Start-Process -FilePath $wv -ArgumentList "/silent /install" -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
    } catch {
      Write-Output "WARN:skip webview install"
    }
  }
} else {
  Stage 10 "2/7 webview"
}
Pct 12

function Have-VC {
  $dll = Join-Path $env:WINDIR "System32\vcruntime140.dll"
  if (Test-Path -LiteralPath $dll) { return $true }
  $keys = @(
    "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"
  )
  foreach ($k in $keys) { if (Test-Path $k) { return $true } }
  return $false
}

Stage 16 "3/7 vcredist"
if (-not (Have-VC)) {
  $vc = Join-Path $env:TEMP "bs-vcredist.exe"
  try {
    $okVc = Get-File "https://aka.ms/vs/17/release/vc_redist.x64.exe" $vc 12 16 "3/7 vcredist"
    if ($okVc) {
      Start-Process -FilePath $vc -ArgumentList "/install /quiet /norestart" -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
    }
  } catch {
    Write-Output "WARN:skip vcredist"
  }
}
Pct 72

$py = Join-Path $runtime "python\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
  $pyZip = Join-Path $runtime "python-embed.zip"
  if (Get-File "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip" $pyZip 72 80 "5/7 python") {
    Stage 80 "5/7 python"
    $pyDir = Join-Path $runtime "python"
    try {
      Expand-Archive -Force -LiteralPath $pyZip -DestinationPath $pyDir
      Remove-Item -LiteralPath $pyZip -Force -ErrorAction SilentlyContinue
    } catch {
      Write-Output "WARN:skip python unpack"
    }
  }
} else {
  Stage 84 "5/7 python"
}

# pip her kurulumda garanti edilir (python klasörü önceden var olsa bile).
function Ensure-Pip {
  $pyDir = Split-Path -Parent $py
  # 1) ._pth onarımı: "import site" olmadan site-packages görünmez.
  $zip = Get-ChildItem -LiteralPath $pyDir -Filter "python3*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($zip) {
    $pth = Join-Path $pyDir ($zip.BaseName + "._pth")
    if (-not (Test-Path -LiteralPath $pth)) {
      Set-Content -LiteralPath $pth -Value "$($zip.Name)`n.`nimport site" -Encoding ascii
    } else {
      # Dikkat: taze embedded pakette satir "#import site" olarak KAPALI gelir.
      # Yorum satiri gercek ayar degildir; acik (yorumsuz) satir aranir.
      $acik = @(Get-Content -LiteralPath $pth) | Where-Object { $_.Trim() -eq "import site" }
      if (-not $acik) { Add-Content -LiteralPath $pth -Value "import site" }
    }
  }
  & $py -m pip --version *> $null
  if ($LASTEXITCODE -eq 0) { return }
  # 2) pip 24.0 wheel dogrudan site-packages'a acilir. Wheel saf-Python bir
  #    zip'tir; acmak gecerli kurulumdur. get-pip.py kullanilmaz cunku guncel
  #    pip zip icinden calisirken paket kuramiyor; ayrica gomulu Python,
  #    ._pth varken PYTHONPATH'i yok saydigindan -m pip hilesi de calismaz.
  Stage 82 "5/7 pip"
  $pipWhl = Join-Path $runtime "pip-24.0-py3-none-any.whl"
  if (Get-File "https://files.pythonhosted.org/packages/8a/6a/19e9fe04fca059ccf770861c7d5721ab4c2aebc539889e97c7977528a53b/pip-24.0-py3-none-any.whl" $pipWhl 82 84 "5/7 pip") {
    $site = Join-Path $pyDir "Lib\site-packages"
    New-Item -ItemType Directory -Force -Path $site | Out-Null
    $pipZip = "$pipWhl.zip"
    Copy-Item -LiteralPath $pipWhl -Destination $pipZip -Force
    Expand-Archive -Force -LiteralPath $pipZip -DestinationPath $site
    Remove-Item -LiteralPath $pipZip -Force -ErrorAction SilentlyContinue
  }
}
if (Test-Path -LiteralPath $py) {
  try { Ensure-Pip } catch { Write-Output "WARN:pip bootstrap" }
}
Pct 85

Stage 86 "6/7 mcp"
if (Test-Path -LiteralPath $py) {
  $reqFile = Join-Path $PSScriptRoot "requirements.txt"
  $wheels = Join-Path $PSScriptRoot "wheels"
  if (Test-Path -LiteralPath $wheels) {
    $local = @(Get-ChildItem -LiteralPath $wheels -Filter "*.whl" -ErrorAction SilentlyContinue)
    if ($local.Count -gt 0) {
      & $py -m pip install --force-reinstall @($local.FullName)
    }
  }
  $pkgs = @("httpx>=0.27.0", "anyio>=4.0.0", "mcp>=1.6.0")
  if (Test-Path -LiteralPath $reqFile) {
    $pkgs = @(Get-Content -LiteralPath $reqFile | Where-Object { $_.Trim() -and -not $_.StartsWith("#") })
  }
  foreach ($pkg in $pkgs) {
    try {
      & $py -m pip install --disable-pip-version-check $pkg
      if ($LASTEXITCODE -ne 0) { Write-Output ("WARN:pip " + $pkg) }
    } catch {
      Write-Output ("WARN:pip " + $pkg)
    }
  }
} else {
  Write-Output "WARN:skip mcp no python"
}
Pct 94

Stage 100 "done"
Write-Output ("OK:{0}" -f $desktopFolder)
Pct 100
exit 0
