@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Traz o radar.db da release "dados" do GitHub, para um computador
rem novo arrancar sem ter de recolher onze anos de anuncios outra vez.
rem O contratos.db nao vem por aqui -- refaz-se com
rem "python radar.py --contratos", que demora minutos, nao horas.

if exist "%~dp0radar.db" (
  echo Ja ha um radar.db nesta pasta. Para nao arriscar substituir dados
  echo mais recentes por um transporte antigo, este script nao mexe nele.
  echo Se e mesmo para trazer o de fora, muda-lhe o nome a mao primeiro
  echo -- por exemplo radar-antes-de-trazer.db -- e volta a correr isto.
  pause
  exit /b 1
)

echo A trazer o radar.db da release "dados" do GitHub (mais de 1 GB, demora)...
gh release download dados --pattern "radar.db" --dir "%~dp0"
if errorlevel 1 (
  echo Falhou. Confirma que ha uma release "dados" com o radar.db anexado
  echo -- o publicar_dados.bat cria-a -- e que o "gh auth status" esta bem.
  pause
  exit /b 1
)

echo.
echo Pronto: radar.db trazido. Falta o contratos.db -- corre agora:
echo   python radar.py --contratos
echo (ou o contratos.bat) para o reconstruir a partir do dump publico.
pause
