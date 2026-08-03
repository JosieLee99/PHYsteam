@echo off
:: uninstall.bat
:: Closes PHYsteam and removes it from startup.

:: ── Check for admin rights ────────────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)

echo.
echo  PHYsteam Uninstaller
echo  ----------------------------
echo.

:: ── Confirm before proceeding ─────────────────────────────────────────────────
set /p CONFIRM="This will stop PHYsteam and remove it from startup. Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

:: ── Kill any running physteam.py processes ──────────────────────────────────
echo.
echo  Stopping PHYsteam...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*physteam*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: Small wait to let processes fully terminate
timeout /t 2 /nobreak >nul

echo  Done.

:: ── Remove from Task Scheduler ────────────────────────────────────────────────
echo.
echo  Removing from startup...
schtasks /delete /tn "PHYsteam" /f >nul 2>&1
if %errorLevel% equ 0 (
    echo  Removed from Task Scheduler.
) else (
    echo  No startup task found (already removed or never registered).
)

echo.
echo  Uninstall complete! PHYsteam has been removed from your system.
echo.
pause
