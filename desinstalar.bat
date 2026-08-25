@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Remove as tarefas automaticas e os pacotes instalados.
pause
schtasks /Delete /TN "Radar DR 09h" /F 2>nul
schtasks /Delete /TN "Radar DR 17h" /F 2>nul
python -m pip uninstall -y flask requests
echo.
echo Feito. Apaga agora esta pasta a mao.
pause
