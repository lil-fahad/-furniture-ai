@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
set "FURNITURE_EXIT_CODE=1"
if not exist "%~dp0scripts\windows_launcher.py" goto incomplete
if defined FURNITURE_PYTHON goto explicit_python
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 goto python_launcher
set "FURNITURE_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%FURNITURE_PYTHON%" goto explicit_python
set "FURNITURE_PYTHON=%ProgramFiles%\Python312\python.exe"
if exist "%FURNITURE_PYTHON%" goto explicit_python
if not "%~1"=="" goto missing_python
echo A Python 3.12 installation is needed to open Furniture AI.
call "%~dp0INSTALL-PYTHON.cmd"
if errorlevel 1 goto finish
set "FURNITURE_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%FURNITURE_PYTHON%" goto explicit_python
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 goto python_launcher
:missing_python
echo Python 3.12 64-bit was not found.
echo Open INSTALL-PYTHON.cmd in this folder, then open START-WINDOWS.cmd again.
echo Project folder: "%~dp0"
goto finish

:python_launcher
if "%~1"=="" goto gui_launcher
py -3.12 "%~dp0scripts\windows_train.py" %*
set "FURNITURE_EXIT_CODE=%ERRORLEVEL%"
goto finish
:gui_launcher
py -3.12 "%~dp0scripts\windows_launcher.py"
set "FURNITURE_EXIT_CODE=%ERRORLEVEL%"
goto finish

:explicit_python
"%FURNITURE_PYTHON%" -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto wrong_python
if "%~1"=="" goto gui_explicit
"%FURNITURE_PYTHON%" "%~dp0scripts\windows_train.py" %*
set "FURNITURE_EXIT_CODE=%ERRORLEVEL%"
goto finish
:gui_explicit
"%FURNITURE_PYTHON%" "%~dp0scripts\windows_launcher.py"
set "FURNITURE_EXIT_CODE=%ERRORLEVEL%"
goto finish
:wrong_python
echo The selected Python must be version 3.12, 64-bit. Open INSTALL-PYTHON.cmd.
goto finish
:incomplete
echo Extract ALL files from FurnitureAI-Windows-v2.zip first.
echo Do not run this file from inside the ZIP or copy it away from the scripts folder.
:finish
if "%FURNITURE_EXIT_CODE%"=="0" exit /b 0
if not "%FURNITURE_NO_PAUSE%"=="1" pause
exit /b %FURNITURE_EXIT_CODE%
