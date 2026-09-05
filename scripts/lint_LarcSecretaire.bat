@echo off
echo Linting LarcSecretaire...
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py LarcSecretaire
pause
