@echo off
rem Screen Command 开发启动（全部依赖在项目 .venv，无系统安装）
cd /d "%~dp0"
.venv\Scripts\python -m screen_command run
