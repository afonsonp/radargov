@echo off
rem Mede de onde vem o token das capturas do DR (medir_captura.py).
rem Le as capturas, nunca as escreve; o relatorio abre no Bloco de Notas.
cd /d "%~dp0"
call "%~dp0_python.bat"
"%PY%" medir_captura.py
if exist "amostras\medicao_captura.txt" start notepad "amostras\medicao_captura.txt"
pause
