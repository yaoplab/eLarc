@echo off
echo Linting LarcHub...
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py LarcHub
pause
