@echo off
echo Linting LarcProf...
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py LarcProf
pause
