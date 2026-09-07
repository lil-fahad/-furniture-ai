@echo off
setlocal EnableExtensions DisableDelayedExpansion
where winget >nul 2>&1
if errorlevel 1 goto manual
echo Installing Python 3.12 for your Windows user account.
winget install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64 --accept-package-agreements --accept-source-agreements
set "FURNITURE_EXIT_CODE=%ERRORLEVEL%"
if not "%FURNITURE_EXIT_CODE%"=="0" goto failed
echo Python installation finished. Open START-WINDOWS.cmd next.
pause
exit /b 0
:manual
echo Windows Package Manager was not found.
echo Install Python 3.12 64-bit with Tcl/Tk from https://www.python.org/downloads/windows/
echo Then open START-WINDOWS.cmd again.
pause
exit /b 1
:failed
echo Installation did not complete. Read the Windows Package Manager message above.
pause
exit /b %FURNITURE_EXIT_CODE%
