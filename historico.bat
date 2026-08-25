@echo off
cd /d "%~dp0"
echo A abrir o historico de alteracoes...
start "" gitk --all
