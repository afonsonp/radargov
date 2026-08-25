@echo off
cd /d "%~dp0"
echo A instalar o que falta...
python -m pip install -r requirements.txt
echo.
echo Pronto. Abre agora o iniciar.bat.
pause
