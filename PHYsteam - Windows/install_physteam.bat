@echo off
:: install_physteam.bat
:: Run this ONCE as Administrator to register PHYsteam.exe to start with Windows.

:: ── Check for admin rights ────────────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)

:: ── Build paths ───────────────────────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "WATCHER_EXE=%SCRIPT_DIR%\PHYsteam.exe"

if not exist "%WATCHER_EXE%" (
    echo ERROR: PHYsteam.exe not found in %SCRIPT_DIR%
    echo Make sure install_physteam.bat and PHYsteam.exe are in the same folder.
    pause
    exit /b 1
)

:: ── Register the Task Scheduler task ─────────────────────────────────────────
set "TASK_NAME=PHYsteam"
set "TASK_CMD=\"%WATCHER_EXE%\""

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

schtasks /create /tn "%TASK_NAME%" /tr "%TASK_CMD%" /sc ONLOGON /rl HIGHEST /f >nul

if %errorLevel% equ 0 (
    echo.
    echo  Success! PHYsteam will now start automatically at login.
    echo.
    echo  PHYsteam executable: %WATCHER_EXE%
    echo  Log file           : %SCRIPT_DIR%\physteam.log
    echo.
    echo  Starting PHYsteam setup...
    start "" "%WATCHER_EXE%" --configure
    echo  Done! Insert your game cartridge to test it.
) else (
    echo ERROR: Failed to create the scheduled task.
)

pause
