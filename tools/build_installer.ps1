param(
    [string]$Python = "python",
    [string]$InnoSetupCompiler = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$specPath = Join-Path $repoRoot "packaging\VeilClip.spec"
$issPath = Join-Path $repoRoot "packaging\VeilClip.iss"
$portableDir = Join-Path $repoRoot "dist-portable"
$installerDir = Join-Path $repoRoot "dist-installer"
$versionInfoPath = Join-Path $repoRoot "packaging\version_info.txt"

$versionMatch = Select-String -Path (Join-Path $repoRoot "utils\config.py") -Pattern '^APP_VERSION = "([^"]+)"$'
if (-not $versionMatch) {
    throw "Could not read APP_VERSION from utils\config.py"
}
$appVersion = $versionMatch.Matches[0].Groups[1].Value
$appVersionParts = $appVersion.Split('.')
while ($appVersionParts.Count -lt 4) {
    $appVersionParts += '0'
}
$fileVersion = ($appVersionParts | Select-Object -First 4) -join ', '
$portableStageDir = Join-Path $portableDir "VeilClip-Portable-$appVersion"
$portableZip = Join-Path $portableDir "VeilClip-Portable-$appVersion.zip"
$portableReleaseTemplate = Join-Path $repoRoot "releases\$appVersion\PORTABLE_RELEASE.txt"
$installerReleaseTemplate = Join-Path $repoRoot "releases\$appVersion\INSTALLER_RELEASE.txt"
$portableReleaseNote = Join-Path $portableDir "VeilClip-Portable-$appVersion-RELEASE.txt"
$installerExe = Join-Path $installerDir "VeilClip-Setup-$appVersion.exe"
$installerReleaseNote = Join-Path $installerDir "VeilClip-Setup-$appVersion-RELEASE.txt"

if (-not (Test-Path $portableReleaseTemplate)) {
    throw "Portable release template not found: $portableReleaseTemplate"
}
if (-not (Test-Path $installerReleaseTemplate)) {
    throw "Installer release template not found: $installerReleaseTemplate"
}

if (-not $InnoSetupCompiler) {
    $candidates = @(
        (Join-Path $repoRoot "tools\InnoSetup\ISCC.exe"),
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $InnoSetupCompiler = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $InnoSetupCompiler) {
    throw "ISCC.exe not found. Install Inno Setup 6 or pass -InnoSetupCompiler."
}

Push-Location $repoRoot
try {
    @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($fileVersion),
    prodvers=($fileVersion),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
            StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Osenpa'),
            StringStruct('FileDescription', 'Open-source offline clipboard manager for Windows'),
            StringStruct('FileVersion', '$appVersion'),
            StringStruct('InternalName', 'VeilClip'),
            StringStruct('OriginalFilename', 'VeilClip.exe'),
            StringStruct('ProductName', 'VeilClip'),
            StringStruct('ProductVersion', '$appVersion')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Path $versionInfoPath -Encoding UTF8

    & $Python -m PyInstaller --noconfirm --clean $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    New-Item -ItemType Directory -Force -Path $portableDir | Out-Null
    New-Item -ItemType Directory -Force -Path $installerDir | Out-Null
    if (Test-Path $portableStageDir) {
        Remove-Item $portableStageDir -Recurse -Force
    }
    if (Test-Path $portableZip) {
        Remove-Item $portableZip -Force
    }
    Copy-Item -Path (Join-Path $repoRoot "dist\VeilClip") -Destination $portableStageDir -Recurse
    Copy-Item -Path $portableReleaseTemplate -Destination (Join-Path $portableStageDir "RELEASE.txt") -Force
    Copy-Item -Path (Join-Path $repoRoot "LICENSE") -Destination (Join-Path $portableStageDir "LICENSE.txt") -Force
    Compress-Archive -Path $portableStageDir -DestinationPath $portableZip -Force
    Copy-Item -Path $portableReleaseTemplate -Destination $portableReleaseNote -Force

    & $InnoSetupCompiler "/DAppVersion=$appVersion" $issPath
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup build failed."
    }
    Copy-Item -Path $installerReleaseTemplate -Destination $installerReleaseNote -Force
}
finally {
    Pop-Location
}
