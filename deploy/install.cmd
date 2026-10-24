@echo off
rem 粗剪 skill 部署入口（免手动准备 Python）：找不到 3.12 就静默装包内自带的那份
setlocal EnableExtensions
chcp 65001 >nul
set "B=%~dp0.."
set "PYEXE="

where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYEXE=py"
  if not errorlevel 1 set "PYARGS=-3.12"
)
if defined PYEXE goto run

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys;sys.exit(0 if sys.version_info[:2]>=(3,8) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)
if defined PYEXE goto run

echo [i] 未检测到可用 Python，先装包内自带的 Python 3.12.10 ...
if not exist "%B%\vendor\python-3.12.10-amd64.exe" goto nopy
start /wait "" "%B%\vendor\python-3.12.10-amd64.exe" /quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_pip=1 Include_launcher=1
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYEXE%" goto nopy

:run
"%PYEXE%" %PYARGS% "%B%\deploy\install.py" %*
exit /b %errorlevel%

:nopy
echo [x] 没能准备好 Python。手动安装 Python 3.12.x（勾选 Add python.exe to PATH）后重跑本脚本。
exit /b 1
