@echo off
title IndexForge-DB Server
cd /d "%~dp0"

echo ========================================================
echo        IndexForge-DB (KD-Tree + R-Tree Search)
echo ========================================================
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    set PYCMD=py
    goto found_py
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set PYCMD=python
    goto found_py
)

if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    set PYCMD="%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    goto found_py
)

echo [ERROR] Python not found. Please ensure Python is installed.
pause
exit /b 1

:found_py
echo Using Python: %PYCMD%
echo.
echo Starting IndexForge-DB server on http://localhost:8004 ...
echo (Opening browser in 2 seconds...)
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8004"

%PYCMD% app.py

pause
