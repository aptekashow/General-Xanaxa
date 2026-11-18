$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\\Scripts\\python.exe")) {
    py -3.12 -m venv .venv
}
$python = Join-Path $PSScriptRoot ".venv\\Scripts\\python.exe"

Write-Host "Устанавливаем зависимости и PyInstaller..."
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-build.txt

Write-Host "Собираем приложение. Сборка может занять продолжительное время..."
& $python -m PyInstaller --noconfirm --clean GeneralXanaxa.spec

if (-not (Test-Path "dist\\GeneralXanaxa\\GeneralXanaxa.exe")) {
    throw "EXE не создан. Проверьте сообщения PyInstaller выше."
}

$iscc = @(
    "$env:ProgramFiles\\Inno Setup 6\\ISCC.exe",
    "$env:ProgramFiles(x86)\\Inno Setup 6\\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "Приложение собрано: dist\\GeneralXanaxa"
    Write-Host "Для создания Setup.exe установите Inno Setup 6 и повторите запуск."
    exit 0
}

& $iscc "installer\\GeneralXanaxa.iss"
Write-Host "Готово: installer\\Output\\GeneralXanaxa-Setup.exe"
