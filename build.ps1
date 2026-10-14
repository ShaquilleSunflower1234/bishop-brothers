$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$assetDirectory = Join-Path $PSScriptRoot 'assets'
$versionFile = Join-Path $PSScriptRoot 'release-version.txt'
python -m PyInstaller --noconfirm --clean --onefile --windowed --name BishopBrothers --version-file $versionFile --collect-all tkinterdnd2 --add-data "$assetDirectory;assets" --distpath dist --workpath build --specpath build app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
