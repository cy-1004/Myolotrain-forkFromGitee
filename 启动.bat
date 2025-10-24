@echo off
chcp 936 > nul
setlocal enabledelayedexpansion

title YOLOv8 Training Platform

:menu
cls
echo ========================================
echo   YOLOv8 Training Platform Launcher
echo ========================================
echo.
echo  1. 初始化项目（GPU环境）
echo  2. 初始化项目（纯CPU环境）
echo  3. 启动系统
echo  4. Exit
echo.
set /p choice=Enter your choice (1-4):

if "%choice%"=="1" goto initialize_gpu
if "%choice%"=="2" goto initialize_cpu
if "%choice%"=="3" goto start
if "%choice%"=="4" exit /b 0
goto menu

:initialize_gpu
cls
echo ========================================
echo   Initializing System (GPU Environment)
echo ========================================
echo.
echo 这将会:
echo - 创建python虚拟环境
echo - 安装PyTorch GPU版本(CUDA 12.6)
echo - 安装其他依赖
echo - 初始化数据库（将删除原数据库）
echo.
set /p confirm=Continue? (y/n):
if /i "%confirm%" neq "y" goto menu

:: Create virtual environment
if not exist venv\Scripts\activate.bat (
  echo Creating virtual environment...
  python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install PyTorch GPU version
echo Installing PyTorch GPU version...
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

echo Installing onnxruntime-gpu..
pip3 install onnxruntime-gpu

:: Install other dependencies
if exist requirements.txt (
  echo Installing other dependencies...
  pip install -r requirements.txt
)
:: Initialize database
echo Initializing database...
python "%~dp0init_db.py"

echo.
echo GPU Environment Initialization complete!
pause
goto menu

:initialize_cpu
cls
echo ========================================
echo   Initializing System (CPU Environment)
echo ========================================
echo.
echo 这将会:
echo - 创建python虚拟环境
echo - 安装PyTorch CPU版本
echo - 安装其他依赖
echo - 初始化数据库（将删除原数据库）
echo.
set /p confirm=Continue? (y/n):
if /i "%confirm%" neq "y" goto menu

:: Create virtual environment
if not exist venv\Scripts\activate.bat (
  echo Creating virtual environment...
  python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install PyTorch CPU version
echo Installing PyTorch CPU version...
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
:: Install FastAPI and Uvicorn
echo Installing FastAPI and Uvicorn...
:: 安装 FastAPI 完整版
pip install fastapi[all]
:: 安装核心依赖
pip install ultralytics python-multipart tensorboard
:: Install other dependencies
echo installing onnxruntime
pip install onnxruntime
if exist requirements.txt (
  echo Installing other dependencies...
  pip install -r requirements.txt
)
:: 安装 PostgreSQL 驱动
echo Installing PostgreSQL dependencies...
pip install psycopg2-binary

:: 新增：安装 SQLAlchemy
echo Installing SQLAlchemy...
pip install sqlalchemy
:: 新增：安装 pydantic
echo Installing pydantic...
pip install pydantic
:: 安装 pydantic-settings
echo Installing pydantic-settings...
pip install pydantic-settings
:: 可选：升级 pip
python -m pip install --upgrade pip



:: Initialize database
echo Initializing database...
python "%~dp0init_db.py"

echo.
echo CPU Environment Initialization complete!
pause
goto menu

:start
cls
echo ========================================
echo   Starting System
echo ========================================
echo.

:: Activate virtual environment
if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
)

:: Start application
echo Starting application...
@REM start "YOLOv8 Platform" cmd /c "cd /d "%~dp0" && python run.py"
start "YOLOv8 Platform" cmd /k "cd /d "%~dp0" && python run.py"

echo.
echo Application started!
echo Web interface: http://localhost:8000
echo.
echo Press any key to return to menu...
pause > nul
goto menu
