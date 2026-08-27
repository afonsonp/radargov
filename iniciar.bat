@echo off
cd /d "%~dp0"
call "%~dp0_python.bat"
"%PY%" radar.py
pause
