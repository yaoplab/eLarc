@echo off
echo Linting LarcRH...
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py LarcRH
pause
