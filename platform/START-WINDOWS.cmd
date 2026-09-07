@echo off
setlocal
cd /d "%~dp0"
py -3.12 scripts\windows_train.py %*
set "FURNITURE_EXIT_CODE=%ERRORLEVEL%"
if not "%FURNITURE_EXIT_CODE%"=="0" echo Read the error above. Python 3.12 and a supported NVIDIA GPU are required for CUDA training.
pause
exit /b %FURNITURE_EXIT_CODE%
