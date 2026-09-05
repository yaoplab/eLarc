@echo off
cd /d %~dp0..
.venv\Scripts\python.exe scripts\lint_all.py %%*
pause
