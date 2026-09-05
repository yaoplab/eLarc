@echo off
echo Linting LarcCompta...
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py LarcCompta
pause
