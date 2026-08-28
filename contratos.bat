@echo off
cd /d "%~dp0"
call "%~dp0_python.bat"
rem Sem anos: traz o ano corrente e o anterior, que e onde entram
rem contratos novos. Anos fechados nao mudam. E o que a tarefa semanal
rem corre, e o mesmo que o botao "Actualizar contratos" do painel faz.
"%PYW%" radar.py --contratos
if errorlevel 1 "%PY%" radar.py --contratos
