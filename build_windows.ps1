$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "Устанавливаем зависимости и PyInstaller..."
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Не удалось обновить pip." }
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Не удалось установить зависимости." }

Write-Host "Собираем приложение. Сборка может занять продолжительное время..."
& $python -m PyInstaller --noconfirm --clean GeneralXanaxa.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller завершился с ошибкой." }

if (-not (Test-Path "dist\GeneralXanaxa\GeneralXanaxa.exe")) {
    throw "EXE не создан. Проверьте сообщения PyInstaller выше."
}

# Ищем Inno Setup в стандартных каталогах и через PATH.
$isccCandidates = @(
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path "${env:ProgramFiles(x86)}" "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ChocolateyInstall "lib\innosetup\tools\ISCC.exe"),
    (Join-Path $env:ChocolateyInstall "lib\innosetup\tools\Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $iscc) {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) { $iscc = $command.Source }
}

if (-not $iscc) {
    throw "Inno Setup установлен, но ISCC.exe не найден. Проверьте установку Inno Setup 6."
}

Write-Host "Компилятор Inno Setup: $iscc"
& $iscc "installer\GeneralXanaxa.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup не смог создать установщик." }

$installer = "installer\Output\GeneralXanaxa-Setup.exe"
if (-not (Test-Path $installer)) {
    throw "Inno Setup завершился, но установщик не найден: $installer"
}
Write-Host "Готово: $installer"
