@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat"
echo.
echo  Remove as tarefas automaticas das 09h e das 17h deste computador.
echo.
if exist "%~dp0python\python.exe" (
  echo  Os pacotes ficam: vivem dentro desta pasta, nao neste computador.
  echo  Para deixar de ter isto aqui, basta tirar a pen.
) else (
  echo  Remove tambem os pacotes que foram instalados neste computador.
)
echo.
pause
schtasks /Delete /TN "Radar DR 09h" /F 2>nul
schtasks /Delete /TN "Radar DR 17h" /F 2>nul
if not exist "%~dp0python\python.exe" "%PY%" -m pip uninstall -y flask requests pypdf cryptography
echo.
echo Feito.
pause
