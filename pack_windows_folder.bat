@echo off
setlocal
cd /d "%~dp0"

chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "BAT_RC=0"

set APP_NAME=AniLog
set APP_VERSION=0.2.0
set APP_VERSION_LABEL=v2.0
set PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
set PIP_TIMEOUT=60
set PYTHON=.venv\Scripts\python.exe
set FLET=.venv\Scripts\flet.exe

rem --- HTTP proxy (Clash / v2rayN mixed port) ---
set PROXY_HOST=127.0.0.1
set PROXY_PORT=7890
set HTTP_PROXY=http://%PROXY_HOST%:%PROXY_PORT%
set HTTPS_PROXY=%HTTP_PROXY%
set ALL_PROXY=%HTTP_PROXY%
set NO_PROXY=localhost,127.0.0.1,::1

echo ============================================
echo  AniLog - Windows folder pack (PyInstaller onedir)
echo ============================================

if not exist "%PYTHON%" (
    echo [ERROR] .venv not found. Run the project setup first.
    goto :fail
)
if not exist "%FLET%" (
    echo [ERROR] flet CLI not found in .venv.
    goto :fail
)
if not exist "assets" (
    echo [ERROR] assets directory not found.
    goto :fail
)

echo [INFO] Checking PyInstaller...
"%PYTHON%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    "%PYTHON%" -m pip install pyinstaller -i %PIP_INDEX% --timeout %PIP_TIMEOUT%
    if errorlevel 1 (
        echo [ERROR] PyInstaller installation failed.
        goto :fail
    )
)

echo [INFO] Packing into a folder (onedir)...
rem Run flet pack in a separate workdir to avoid clearing project build dir.
set "PACK_WORK=%~dp0build_pack_windows"
if not exist "%PACK_WORK%" mkdir "%PACK_WORK%"
set "PYTHONPATH=%~dp0"
pushd "%PACK_WORK%"
"%~dp0.venv\Scripts\flet.exe" pack "%~dp0main.py" ^
    -D ^
    -n %APP_NAME% ^
    -i "%~dp0assets\pic\icon.ico" ^
    --product-name %APP_NAME% ^
    --product-version %APP_VERSION% ^
    --file-description "AniLog" ^
    --add-data "%~dp0assets;assets" ^
    --add-data "%~dp0.venv\Lib\site-packages\pykakasi\data;pykakasi\data" ^
    --distpath "%~dp0dist" ^
    -y
set "PACK_RC=%errorlevel%"
popd

if not "%PACK_RC%"=="0" (
    echo [ERROR] flet pack failed.
    echo Check the PyInstaller output above.
    goto :fail
)

echo [INFO] Compressing dist\%APP_NAME%...
tar -a -c -f "dist\%APP_NAME%-%APP_VERSION_LABEL%-windows-x86_64.zip" -C "dist" "%APP_NAME%"
if errorlevel 1 (
    echo [ERROR] Failed to create the zip archive.
    goto :fail
)

echo.
echo [OK] Folder build created.
echo Output folder: dist\%APP_NAME%
echo Output zip:    dist\%APP_NAME%-%APP_VERSION_LABEL%-windows-x86_64.zip
goto :done

:fail
set "BAT_RC=1"
echo.
echo [FAILED] Pack did not finish. Check the messages above.

:done
if /i "%NO_PAUSE%"=="1" goto :end
echo.
echo Press any key to close this window...
pause >nul

:end
endlocal & exit /b %BAT_RC%
