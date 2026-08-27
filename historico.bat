@echo off
cd /d "%~dp0"
rem Numa pen (FAT32) o git recusa-se a abrir o repositorio: o sistema de
rem ficheiros nao guarda dono, e o git ve isso como suspeito. Estas tres
rem variaveis dizem-lhe que confie, so nesta janela -- ao contrario do
rem "git config --global", nao deixam rasto no computador onde a pen
rem estiver espetada, que e todo o ponto de ter isto numa pen.
set GIT_CONFIG_COUNT=1
set GIT_CONFIG_KEY_0=safe.directory
set GIT_CONFIG_VALUE_0=*
echo A abrir o historico de alteracoes...
start "" gitk --all
