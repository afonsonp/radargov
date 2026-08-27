@echo off
rem Escolhe que Python usar, e e chamado por todos os outros .bat.
rem
rem Se houver um Python dentro da pasta (pasta "python"), e esse que
rem manda: e o caso da pen, onde a aplicacao anda com o seu proprio
rem motor e nao depende de nada instalado na maquina.
rem
rem Se nao houver, usa-se o do sistema -- que e como isto sempre
rem funcionou, e continua a funcionar num computador onde o Python
rem esteja instalado.
if exist "%~dp0python\python.exe" (
  set "PY=%~dp0python\python.exe"
  set "PYW=%~dp0python\pythonw.exe"
  set "ONDE=o Python da pasta"
) else (
  set "PY=python"
  set "PYW=pythonw"
  set "ONDE=o Python instalado no computador"
)
