@echo off
cd /d "%~dp0"
echo A criar as tarefas das 09:00 e das 17:00...
echo.
schtasks /Create /TN "Radar DR 09h" /TR "\"%~dp0verificar.bat\"" /SC DAILY /ST 09:00 /F
schtasks /Create /TN "Radar DR 17h" /TR "\"%~dp0verificar.bat\"" /SC DAILY /ST 17:00 /F
echo.
echo Feito. Verifica sozinho, mesmo com o painel fechado.
pause
