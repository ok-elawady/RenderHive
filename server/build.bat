@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  RenderHive Server — Build Script (Optimized Fast Pipeline)
REM  Produces all artifacts needed to compile the Inno Setup
REM  installer (RenderHiveServerSetup.iss).
REM ============================================================

echo.
echo ============================================================
echo  RenderHive Server Builder (Fast Mode)
echo ============================================================
echo.

REM --- Locate a suitable Python executable ---
set PYTHON_EXE=python
if exist ..\backend\.venv\Scripts\python.exe (
    set PYTHON_EXE=..\backend\.venv\Scripts\python.exe
    echo Using backend venv Python: !PYTHON_EXE!
) else (
    echo Using system Python: %PYTHON_EXE%
)

REM --- Directories ---
set STAGING=staging
set STAGING_MANAGER=%STAGING%\manager
set STAGING_API=%STAGING%\api
set STAGING_FRONTEND=%STAGING%\frontend
set STAGING_POSTGRES=%STAGING%\postgres
set STAGING_REDIS=%STAGING%\redis
set STAGING_NGINX=%STAGING%\nginx
set STAGING_NSSM=%STAGING%\nssm
set STAGING_ASSETS=%STAGING%\assets
set STAGING_AI=%STAGING%\ai

echo [1/9] Preparing staging directories...
if not exist %STAGING% mkdir %STAGING%
if not exist %STAGING_POSTGRES% mkdir %STAGING_POSTGRES%
if not exist %STAGING_REDIS% mkdir %STAGING_REDIS%
if not exist %STAGING_NGINX% mkdir %STAGING_NGINX%
if not exist %STAGING_NSSM% mkdir %STAGING_NSSM%
if not exist %STAGING_ASSETS% mkdir %STAGING_ASSETS%
if not exist %STAGING_AI% mkdir %STAGING_AI%

REM Only clean dynamic code build targets
if exist %STAGING_MANAGER% rmdir /s /q %STAGING_MANAGER%
if exist %STAGING_API% rmdir /s /q %STAGING_API%
if exist %STAGING_FRONTEND% rmdir /s /q %STAGING_FRONTEND%
mkdir %STAGING_MANAGER%
mkdir %STAGING_API%
mkdir %STAGING_FRONTEND%

REM ============================================================
REM  STEP 2: Build the Server Manager GUI (PyInstaller)
REM ============================================================
echo.
echo [2/9] Building Server Manager GUI (PyInstaller)...
if not exist .venv (
    %PYTHON_EXE% -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install -q -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

pyinstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --noupx ^
    --name "RenderHiveServer" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --paths "..\worker" ^
    --uac-admin ^
    manager_app.py

if errorlevel 1 (
    echo ERROR: PyInstaller failed for manager_app.py
    goto :error
)
xcopy /e /q /y dist\RenderHiveServer\* %STAGING_MANAGER%\
echo    Manager GUI built OK.
call deactivate

REM ============================================================
REM  STEP 3: Build the Django API launcher (PyInstaller)
REM ============================================================
echo.
echo [3/9] Building Django API launcher (PyInstaller)...

if not exist .venv_api (
    %PYTHON_EXE% -m venv .venv_api
    call .venv_api\Scripts\activate.bat
    python -m pip install -q -e ..\backend --extra-index-url https://pypi.org/simple
    python -m pip install -q waitress pyinstaller
) else (
    call .venv_api\Scripts\activate.bat
)

pyinstaller ^
    --noconfirm ^
    --onedir ^
    --console ^
    --noupx ^
    --name "RenderHiveAPI" ^
    --icon "assets\icon.ico" ^
    --paths "..\backend" ^
    --add-data "..\backend\apps;apps" ^
    --add-data "..\backend\config;config" ^
    --hidden-import "django.contrib.admin" ^
    --hidden-import "django.contrib.auth" ^
    --hidden-import "django.contrib.contenttypes" ^
    --hidden-import "django.contrib.sessions" ^
    --hidden-import "django.contrib.messages" ^
    --hidden-import "django.contrib.staticfiles" ^
    --collect-submodules "allauth" ^
    --collect-submodules "corsheaders" ^
    --collect-submodules "rest_framework" ^
    --collect-submodules "django_filters" ^
    --collect-submodules "drf_spectacular" ^
    --collect-submodules "django_celery_beat" ^
    --collect-submodules "django_redis" ^
    --collect-submodules "celery" ^
    --collect-submodules "kombu" ^
    --collect-submodules "billiard" ^
    --collect-submodules "vine" ^
    --collect-submodules "amqp" ^
    --collect-submodules "apps" ^
    --hidden-import "waitress" ^
    --hidden-import "environ" ^
    --hidden-import "psycopg" ^
    api_launcher.py

if errorlevel 1 (
    echo ERROR: PyInstaller failed for api_launcher.py
    goto :error
)
xcopy /e /q /y dist\RenderHiveAPI\* %STAGING_API%\
echo    Django API launcher built OK.
call deactivate

REM ============================================================
REM  STEP 3.5: Build the AI Service (PyInstaller)
REM ============================================================
echo.
echo [3.5/9] Building AI Service (PyInstaller)...

if not exist .venv_ai (
    %PYTHON_EXE% -m venv .venv_ai
    call .venv_ai\Scripts\activate.bat
    python -m pip install -q -r ..\services\ai_service\requirements.txt
    python -m pip install -q pyinstaller
) else (
    call .venv_ai\Scripts\activate.bat
)

pyinstaller ^
    --noconfirm ^
    --onedir ^
    --console ^
    --noupx ^
    --name "RenderHiveAI" ^
    --icon "assets\icon.ico" ^
    --paths "..\services\ai_service" ^
    --hidden-import "llama_cpp" ^
    --hidden-import "pydantic" ^
    --hidden-import "fastapi" ^
    --hidden-import "uvicorn" ^
    --hidden-import "httpx" ^
    --hidden-import "aiofiles" ^
    --collect-all "llama_cpp" ^
    ..\services\ai_service\main.py

if errorlevel 1 (
    echo ERROR: PyInstaller failed for AI Service
    goto :error
)
xcopy /e /q /y dist\RenderHiveAI\* %STAGING_AI%\
echo    AI Service built OK.
call deactivate

REM ============================================================
REM  STEP 4: Build Next.js Static Export
REM ============================================================
echo.
echo [4/9] Building Next.js static export...
pushd ..\frontend

set NEXT_EXPORT=true
set NEXT_PUBLIC_API_URL=http://server.renderhive.local
set NEXT_TELEMETRY_DISABLED=1

call pnpm build
set NEXT_EXPORT=
if errorlevel 1 (
    popd
    echo ERROR: Next.js build failed
    goto :error
)

popd
xcopy /e /q /y ..\frontend\out\* %STAGING_FRONTEND%\
echo    Frontend static export built OK.

REM ============================================================
REM  STEP 5: PostgreSQL 16 (Windows ZIP)
REM ============================================================
echo.
echo [5/9] Checking PostgreSQL 16 binaries...

set PG_VERSION=16.9-1
set PG_ZIP=postgresql-%PG_VERSION%-windows-x64-binaries.zip
set PG_URL=https://get.enterprisedb.com/postgresql/%PG_ZIP%
set PG_DOWNLOAD=downloads\%PG_ZIP%

if not exist downloads mkdir downloads

if exist %STAGING_POSTGRES%\bin\postgres.exe (
    echo    PostgreSQL already extracted in staging - skipping.
) else (
    if not exist %PG_DOWNLOAD% (
        echo    Downloading %PG_URL%...
        curl -f -L --progress-bar -o %PG_DOWNLOAD% %PG_URL%
        if errorlevel 1 (
            echo ERROR: Failed to download PostgreSQL
            goto :error
        )
    ) else (
        echo    Using cached %PG_DOWNLOAD%
    )

    echo    Extracting PostgreSQL...
    tar -xf %PG_DOWNLOAD% -C %STAGING_POSTGRES% --strip-components=1
    echo    PostgreSQL extracted OK.
)

REM ============================================================
REM  STEP 6: Redis for Windows
REM ============================================================
echo.
echo [6/9] Checking Redis for Windows...

set REDIS_VERSION=5.0.14.1
set REDIS_ZIP=Redis-x64-%REDIS_VERSION%.zip
set REDIS_URL=https://github.com/tporadowski/redis/releases/download/v%REDIS_VERSION%/%REDIS_ZIP%
set REDIS_DOWNLOAD=downloads\%REDIS_ZIP%

if exist %STAGING_REDIS%\redis-server.exe (
    echo    Redis already extracted in staging - skipping.
) else (
    if not exist %REDIS_DOWNLOAD% (
        echo    Downloading %REDIS_URL%...
        curl -f -L --progress-bar -o %REDIS_DOWNLOAD% %REDIS_URL%
        if errorlevel 1 (
            echo ERROR: Failed to download Redis
            goto :error
        )
    ) else (
        echo    Using cached %REDIS_DOWNLOAD%
    )

    echo    Extracting Redis...
    tar -xf %REDIS_DOWNLOAD% -C %STAGING_REDIS%
    echo    Redis extracted OK.
)

REM ============================================================
REM  STEP 7: nginx for Windows
REM ============================================================
echo.
echo [7/9] Checking nginx for Windows...

set NGINX_VERSION=1.27.4
set NGINX_ZIP=nginx-%NGINX_VERSION%.zip
set NGINX_URL=https://nginx.org/download/%NGINX_ZIP%
set NGINX_DOWNLOAD=downloads\%NGINX_ZIP%

if exist %STAGING_NGINX%\nginx.exe (
    echo    nginx already extracted in staging - skipping.
) else (
    if not exist %NGINX_DOWNLOAD% (
        echo    Downloading %NGINX_URL%...
        curl -f -L --progress-bar -o %NGINX_DOWNLOAD% %NGINX_URL%
        if errorlevel 1 (
            echo ERROR: Failed to download nginx
            goto :error
        )
    ) else (
        echo    Using cached %NGINX_DOWNLOAD%
    )

    echo    Extracting nginx...
    tar -xf %NGINX_DOWNLOAD% -C %STAGING_NGINX% --strip-components=1
    echo    nginx extracted OK.
)

REM ============================================================
REM  STEP 8: NSSM
REM ============================================================
echo.
echo [8/9] Checking NSSM...

set NSSM_VERSION=2.24
set NSSM_ZIP=nssm-%NSSM_VERSION%.zip
set NSSM_URL=https://nssm.cc/release/%NSSM_ZIP%
set NSSM_DOWNLOAD=downloads\%NSSM_ZIP%

if exist %STAGING_NSSM%\nssm.exe (
    echo    NSSM already extracted in staging - skipping.
) else (
    if not exist %NSSM_DOWNLOAD% (
        echo    Downloading %NSSM_URL%...
        curl -f -L --progress-bar -o %NSSM_DOWNLOAD% %NSSM_URL%
        if errorlevel 1 (
            echo ERROR: Failed to download NSSM
            goto :error
        )
    ) else (
        echo    Using cached %NSSM_DOWNLOAD%
    )

    echo    Extracting NSSM...
    tar -xf %NSSM_DOWNLOAD% -C %STAGING_NSSM%
    for /d %%d in (%STAGING_NSSM%\nssm-*) do (
        copy /y "%%d\win64\nssm.exe" %STAGING_NSSM%\nssm.exe > nul
        rmdir /s /q "%%d"
    )
    echo    NSSM extracted OK.
)

REM ============================================================
REM  Copy assets and templates
REM ============================================================
copy /y assets\icon.ico %STAGING_ASSETS%\ > nul
copy /y assets\icon.png %STAGING_ASSETS%\ > nul
if exist assets\icon.svg copy /y assets\icon.svg %STAGING_ASSETS%\ > nul
copy /y post_install.ps1 %STAGING%\ > nul

if not exist %STAGING_NGINX%\conf mkdir %STAGING_NGINX%\conf
(
echo events {}
echo.
echo http {
echo     include       mime.types;
echo     default_type  application/octet-stream;
echo     sendfile      on;
echo     server_names_hash_bucket_size 64;
echo.
echo     server {
echo         listen 80;
echo         server_name renderhive.local;
echo.
echo         root "RENDERHIVE_FRONTEND_ROOT";
echo         index index.html;
echo.
echo         location / {
echo             try_files ^$uri ^$uri/ /index.html;
echo         }
echo     }
echo.
echo     server {
echo         listen 80;
echo         server_name server.renderhive.local;
echo.
echo         location / {
echo             proxy_pass http://127.0.0.1:8000;
echo             proxy_http_version 1.1;
echo             proxy_set_header Host ^$host;
echo             proxy_set_header X-Real-IP ^$remote_addr;
echo             proxy_set_header X-Forwarded-For ^$proxy_add_x_forwarded_for;
echo             proxy_set_header X-Forwarded-Proto ^$scheme;
echo         }
echo.
echo         location /static/ {
echo             alias "RENDERHIVE_INSTALL_DIR/api/staticfiles/";
echo         }
echo     }
echo }
) > %STAGING_NGINX%\conf\nginx.conf.template

REM ============================================================
REM Check common installation paths for Inno Setup 6 and 7
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC (
    echo.
    echo [9/9] Compiling Installer - Inno Setup...
    "%ISCC%" RenderHiveServerSetup.iss
    if errorlevel 1 (
        echo ERROR: Inno Setup compilation failed.
        goto :error
    )
    echo.
    echo ============================================================
    echo  BUILD COMPLETE! 
    echo  Installer saved to: server\Output\RenderHive Server Setup.exe
    echo ============================================================
    echo.
) else (
    echo.
    echo ============================================================
    echo  STAGING COMPLETE!
    echo ============================================================
    echo.
    echo  Next step:
    echo    Open RenderHiveServerSetup.iss in Inno Setup 6
    echo    and click Build ^> Compile.
    echo ============================================================
    echo.
)

pause
goto :eof

:error
echo.
echo ============================================================
echo  BUILD FAILED. See error above.
echo ============================================================
pause
exit /b 1
