@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat"
if exist "%~dp0python\python.exe" (
  echo.
  echo  Esta pasta traz o seu proprio Python e os seus proprios pacotes,
  echo  nas pastas "python" e "libs". Nao ha nada a instalar neste
  echo  computador.
  echo.
  echo  A confirmar que esta tudo...
  "%PY%" -c "import flask, requests, pypdf, pymupdf; print('   Esta tudo. Abre o iniciar.bat.')"
  echo.
  pause
  exit /b
)
echo A instalar o que falta...
"%PY%" -m pip install -r requirements.txt
echo.
echo Pronto. Abre agora o iniciar.bat.
pause
