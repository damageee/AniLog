@echo off
setlocal
cd /d "%~dp0"

chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "BAT_RC=0"
set APP_VERSION=0.1.0
set PYTHON_VERSION=3.14
set PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
set PIP_TIMEOUT=60
set EXCLUDES=storage chat_history.txt AGENTS.md Anilog_config.json bangumi.xlsx bangumi_import.xlsx fullfill.xlsx .cursor .gitignore AniLog.spec README.md requirements.txt build_windows.bat build_android.bat pack_windows.bat pack_windows_folder.bat dist __pycache__ icon.jpg icon.png icon_android.png tools

rem --- HTTP proxy (Clash / v2rayN mixed port) ---
set PROXY_HOST=127.0.0.1
set PROXY_PORT=7890
set HTTP_PROXY=http://%PROXY_HOST%:%PROXY_PORT%
set HTTPS_PROXY=%HTTP_PROXY%
set ALL_PROXY=%HTTP_PROXY%
set NO_PROXY=localhost,127.0.0.1,::1

echo ============================================
echo  AniLog - Windows build
echo ============================================

where flutter >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Flutter was not found in PATH.
    echo Install Flutter SDK and add its bin directory to PATH first.
    echo Flet build needs Flutter and Visual Studio Build Tools on Windows.
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create .venv. Is Python installed?
        goto :fail
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate .venv.
    goto :fail
)

echo [INFO] Installing requirements...
python -m pip install --upgrade pip -i %PIP_INDEX% --timeout %PIP_TIMEOUT%
python -m pip install -r requirements.txt -i %PIP_INDEX% --timeout %PIP_TIMEOUT%
if errorlevel 1 (
    echo [ERROR] pip install failed.
    goto :fail
)

rem Flet's icon generator ignores .ico, so convert the project icon to PNG.
echo [INFO] Preparing app icon...
set "APP_ICON=icon.jpg"
if exist "%APP_ICON%" (
    python tools\make_icons.py "%APP_ICON%"
    if errorlevel 1 (
        echo [ERROR] Could not generate icons from %APP_ICON%
        goto :fail
    )
) else (
    echo [WARN] %APP_ICON% not found, default icon will be used.
)

echo [INFO] Cleaning stale bundled Python runtime...
for /d %%D in ("build\flutter\build\build_python_*") do rmdir /s /q "%%D" 2>nul

echo [INFO] Building Windows app...
".venv\Scripts\flet.exe" build windows ^
    --project anilog ^
    --product AniLog ^
    --artifact AniLog ^
    --org com.damage ^
    --module-name main ^
    --python-version %PYTHON_VERSION% ^
    --build-version %APP_VERSION% ^
    --exclude %EXCLUDES% ^
    --yes

if errorlevel 1 (
    echo [ERROR] flet build windows failed.
    echo Check the Flutter/Visual Studio output above.
    goto :fail
)

echo.
echo [OK] Windows build finished.
echo Output: build\windows
goto :done

:fail
set "BAT_RC=1"
echo.
echo [FAILED] Build did not finish. Check the messages above.

:done
if /i "%NO_PAUSE%"=="1" goto :end
echo.
echo Press any key to close this window...
pause >nul

:end
endlocal & exit /b %BAT_RC%


