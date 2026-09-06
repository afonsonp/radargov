@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Traz para a pen a ultima release publicada no GitHub -- nunca segue
rem o master a cada commit. A programacao faz-se nas sessoes remotas do
rem Claude Code; aqui so se actualiza quando ha uma tag nova pronta.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo Isto nao e um repositorio git. Nada a actualizar.
  pause
  exit /b 1
)

git diff --quiet
if errorlevel 1 goto suja
git diff --cached --quiet
if errorlevel 1 goto suja
goto limpa

:suja
echo Ha alteracoes por gravar em ficheiros que o git segue -- provavelmente
echo o config.json, mexido pelo painel. Fecha o radar, confirma com
echo "git status" o que e, e faz commit ou "git checkout -- config.json"
echo antes de actualizar.
pause
exit /b 1

:limpa
echo A verificar releases no GitHub...
git fetch --tags --force origin
if errorlevel 1 (
  echo Nao consegui falar com o GitHub. Verifica a ligacao.
  pause
  exit /b 1
)

for /f "delims=" %%T in ('git tag --sort=-v:refname') do (
  set "ULTIMA=%%T"
  goto encontrada
)
:encontrada
if "%ULTIMA%"=="" (
  echo Ainda nao ha nenhuma release no GitHub.
  pause
  exit /b 1
)

for /f "delims=" %%A in ('git rev-parse HEAD') do set "AGORA=%%A"
for /f "delims=" %%B in ('git rev-parse %ULTIMA%^{commit^}') do set "ALVO=%%B"
if "%AGORA%"=="%ALVO%" (
  echo Ja esta na ultima release: %ULTIMA%
  pause
  exit /b 0
)

echo A actualizar de %AGORA:~0,7% para a release %ULTIMA%...
git merge --ff-only %ULTIMA%
if errorlevel 1 (
  echo.
  echo Nao consegui avancar sem misturar historico -- ha commits locais
  echo que a release nao conhece. Nao mexi em nada; resolve isto a mao
  echo com o git antes de voltar a tentar.
  pause
  exit /b 1
)

echo.
echo Pronto. A pen esta agora na release %ULTIMA%.
pause
