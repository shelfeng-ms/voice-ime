# Voice IME — Create Desktop Shortcut
# Run this once to create a shortcut on your desktop that launches Voice IME without a console.

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\Voice IME.lnk")

$ProjectDir = $PSScriptRoot

# Check if we have a built exe
$ExePath = Join-Path $ProjectDir "dist\VoiceIME\VoiceIME.exe"
if (Test-Path $ExePath) {
    # Use built exe
    $Shortcut.TargetPath = $ExePath
    $Shortcut.WorkingDirectory = Join-Path $ProjectDir "dist\VoiceIME"
    Write-Host "Shortcut will launch built .exe" -ForegroundColor Green
} else {
    # Use pythonw.exe (no console) with main.py
    $PythonW = Join-Path $ProjectDir "venv\Scripts\pythonw.exe"
    if (-not (Test-Path $PythonW)) {
        Write-Host "ERROR: pythonw.exe not found at $PythonW" -ForegroundColor Red
        exit 1
    }
    $Shortcut.TargetPath = $PythonW
    $Shortcut.Arguments = "`"$(Join-Path $ProjectDir 'main.py')`""
    $Shortcut.WorkingDirectory = $ProjectDir
    Write-Host "Shortcut will launch via pythonw.exe (no console)" -ForegroundColor Yellow
}

$IconPath = Join-Path $ProjectDir "assets\icon.png"
if (Test-Path $IconPath) {
    # Windows shortcuts need .ico, so we skip custom icon for now
    # The exe build will embed it properly
}

$Shortcut.Description = "Voice IME - Local voice input method"
$Shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created: $DesktopPath\Voice IME.lnk" -ForegroundColor Green
Write-Host "Double-click it to launch Voice IME without a console window!" -ForegroundColor Cyan
