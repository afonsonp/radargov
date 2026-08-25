@echo off
cd /d "%~dp0"
pythonw radar.py --uma-vez
if errorlevel 1 python radar.py --uma-vez
