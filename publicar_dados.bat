@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Envia o radar.db para uma release "dados" no GitHub, para o poder
rem trazer para outro computador com o trazer_dados.bat. So o radar.db:
rem o contratos.db refaz-se em minutos com "python radar.py --contratos"
rem e nao vale a pena transportar 2,5 GB por causa disso.

if not exist "%~dp0radar.db" (
  echo Nao ha radar.db nesta pasta. Nada a enviar.
  pause
  exit /b 1
)

echo ATENCAO: fecha o painel e as tarefas agendadas antes de continuar --
echo enviar o radar.db com o radar a escrever nele pode levar uma copia
echo a meio de uma escrita.
echo.
choice /c SN /m "Ja esta fechado, posso continuar"
if errorlevel 2 exit /b 1

echo.
echo A enviar o radar.db para o GitHub (pode demorar, e mais de 1 GB)...
gh release view dados >nul 2>&1
if errorlevel 1 (
  gh release create dados "%~dp0radar.db" --title "Base de dados (radar.db)" --notes "Ultima base enviada por publicar_dados.bat."
) else (
  gh release upload dados "%~dp0radar.db" --clobber
)
if errorlevel 1 (
  echo Falhou o envio. Verifica a ligacao e o "gh auth status".
  pause
  exit /b 1
)

echo.
echo Pronto. A base esta na release "dados" do GitHub.
pause
