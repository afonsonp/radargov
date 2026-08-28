@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo A criar as tarefas do Radar...
echo.

rem As duas verificacoes diarias. Sem estas, o radar so recolhe quando o
rem painel esta aberto -- e o relogio interno recupera os slots falhados,
rem o que faz parecer que correu a horas quando nao correu.
schtasks /Create /TN "Radar DR 09h" /TR "\"%~dp0verificar.bat\"" /SC DAILY /ST 09:00 /F
schtasks /Create /TN "Radar DR 17h" /TR "\"%~dp0verificar.bat\"" /SC DAILY /ST 17:00 /F

rem O corpus de contratos do Portal BASE. O dump do IMPIC e semanal, por
rem isso mais do que uma vez por semana nao traz nada de novo. A segunda
rem de manha, porque o dump costuma sair ao fim de semana.
schtasks /Create /TN "Radar contratos (semanal)" /TR "\"%~dp0contratos.bat\"" /SC WEEKLY /D MON /ST 08:00 /F

echo.
echo Feito. Tres tarefas criadas:
echo   Radar DR 09h                 todos os dias as 09:00
echo   Radar DR 17h                 todos os dias as 17:00
echo   Radar contratos (semanal)    segundas as 08:00
echo.
echo O radar passa a recolher com o painel fechado.
pause
