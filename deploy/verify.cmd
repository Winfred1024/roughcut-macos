@echo off
rem 部署后自检：3 项 smoke + 字幕链路 + 路径残留扫描
setlocal EnableExtensions
chcp 65001 >nul
set "B=%~dp0.."
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%B%\deploy\verify.py" %*
) else (
  py -3.12 "%B%\deploy\verify.py" %*
)
exit /b %errorlevel%
