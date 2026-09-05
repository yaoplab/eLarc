@echo off
echo Linting LarcCommon...
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py LarcCommon
pause
