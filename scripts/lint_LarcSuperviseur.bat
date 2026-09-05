@echo off
echo Linting LarcSuperviseur...
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py LarcSuperviseur
pause
