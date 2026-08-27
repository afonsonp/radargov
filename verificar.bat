@echo off
cd /d "%~dp0"
call "%~dp0_python.bat"
"%PYW%" radar.py --uma-vez
if errorlevel 1 "%PY%" radar.py --uma-vez
