@echo off
setlocal
cd /d "%~dp0"
if not exist ".build-env\Scripts\python.exe" (
    py -3.10 -m venv .build-env
    if errorlevel 1 goto failed
)
".build-env\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 goto failed
".build-env\Scripts\python.exe" scripts\build.py
if errorlevel 1 goto failed
echo.
echo Build complete. The portable ZIP is in the release folder.
pause
exit /b 0
:failed
echo.
echo Build failed. See the error above. Windows x64 Python 3.10 with Tcl/Tk is required.
pause
exit /b 1
