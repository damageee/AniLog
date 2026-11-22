@echo off
setlocal
cd /d "%~dp0"

chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "BAT_RC=0"
set EXCLUDES=storage chat_history.txt AGENTS.md Anilog_config.json bangumi.xlsx bangumi_import.xlsx fullfill.xlsx .cursor .gitignore AniLog.spec README.md requirements.txt build_windows.bat build_android.bat pack_windows.bat pack_windows_folder.bat dist __pycache__ icon.jpg icon.png icon_android.png tools testfile backup build_pack_windows .venv build release releases .opencode .vscode .readme .git

rem --- HTTP proxy (Clash / v2rayN mixed port) ---
set PROXY_HOST=127.0.0.1
set PROXY_PORT=7890
set HTTP_PROXY=http://%PROXY_HOST%:%PROXY_PORT%
set HTTPS_PROXY=%HTTP_PROXY%
set ALL_PROXY=%HTTP_PROXY%
set NO_PROXY=localhost,127.0.0.1,::1

rem The bundled python's pip sometimes loses its vendored CA bundle on repeated
rem target installs; point pip at the venv's certifi so HTTPS keeps working.
set "CERT_BUNDLE=%~dp0.venv\Lib\site-packages\certifi\cacert.pem"
if exist "%CERT_BUNDLE%" (
    set "PIP_CERT=%CERT_BUNDLE%"
    set "SSL_CERT_FILE=%CERT_BUNDLE%"
)

rem Gradle wrapper, sdkmanager, Kotlin daemon are JVMs and ignore the env vars above
set "JAVA_TOOL_OPTIONS=-Dhttp.proxyHost=%PROXY_HOST% -Dhttp.proxyPort=%PROXY_PORT% -Dhttps.proxyHost=%PROXY_HOST% -Dhttps.proxyPort=%PROXY_PORT% -Dhttp.nonProxyHosts=localhost|127.0.0.1"
set "GRADLE_OPTS=-Dhttp.proxyHost=%PROXY_HOST% -Dhttp.proxyPort=%PROXY_PORT% -Dhttps.proxyHost=%PROXY_HOST% -Dhttps.proxyPort=%PROXY_PORT%"

echo ============================================
echo  AniLog - Android APK build
echo ============================================

where flutter >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Flutter was not found in PATH.
    echo Install Flutter SDK and add its bin directory to PATH first.
    goto :fail
)

where java >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Java was not found in PATH.
    echo Install a JDK / Android Studio and configure JAVA_HOME.
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

python -c "from bangumi.version import APP_VERSION; print(APP_VERSION)" > "%TEMP%\anilog_app_version.txt" 2>nul
set /p APP_VERSION=<"%TEMP%\anilog_app_version.txt"
del "%TEMP%\anilog_app_version.txt" >nul 2>nul
python -c "from bangumi.version import APP_VERSION_LABEL; print(APP_VERSION_LABEL)" > "%TEMP%\anilog_app_version_label.txt" 2>nul
set /p APP_VERSION_LABEL=<"%TEMP%\anilog_app_version_label.txt"
del "%TEMP%\anilog_app_version_label.txt" >nul 2>nul
if not defined APP_VERSION (
    echo [ERROR] Could not read APP_VERSION from bangumi.version.
    goto :fail
)
if not defined APP_VERSION_LABEL (
    echo [ERROR] Could not read APP_VERSION_LABEL from bangumi.version.
    goto :fail
)

echo [INFO] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
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

echo [INFO] Building Android APK...
echo [INFO] Using Python 3.13 for the bundled runtime.
echo [INFO] INTERNET permission is enabled for LAN sync.
".venv\Scripts\flet.exe" build apk ^
    --project anilog ^
    --product AniLog ^
    --artifact AniLog ^
    --org com.damage ^
    --module-name main ^
    --build-version %APP_VERSION% ^
    --python-version 3.13 ^
    --android-permissions android.permission.INTERNET=true ^
    --android-extract-packages pypinyin,pykakasi ^
    --exclude %EXCLUDES% ^
    --split-per-abi ^
    --yes

if errorlevel 1 (
    echo [ERROR] flet build apk failed.
    echo Check the Flutter/Android SDK output above.
    goto :fail
)

rem Keep only the arm64-v8a APK (covers virtually all phones since 2016).
if exist "build\apk" (
    del /q "build\apk\*armeabi-v7a*.apk" >nul 2>nul
    del /q "build\apk\*x86_64*.apk" >nul 2>nul
    del /q "build\apk\*universal*.apk" >nul 2>nul
)

rem Rename the arm64 APK to include the app version label.
if exist "build\apk\AniLog-arm64-v8a.apk" (
    move /y "build\apk\AniLog-arm64-v8a.apk" "build\apk\AniLog-%APP_VERSION_LABEL%-arm64-v8a.apk" >nul
    del /q "build\apk\AniLog-arm64-v8a.apk.sha1" >nul 2>nul
)

echo.
echo [OK] Android APK build finished.
echo Output: build\apk\AniLog-%APP_VERSION_LABEL%-arm64-v8a.apk
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


