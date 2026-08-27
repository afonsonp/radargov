@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat"
echo.
echo  RELER AS PECAS PELO MODELO
echo.
echo  Volta a ler o Caderno de Encargos e o Programa de todos os
echo  concursos que ja tem pecas em disco, e reescreve o Objecto, a
echo  Equipa, os Documentos da proposta e a Localizacao.
echo.
echo  Serve depois de se mexer na forma como o modelo le. Demora cerca
echo  de um minuto por concurso -- nao por ser lento, mas porque a
echo  conta tem um tecto de tokens por minuto e ha que esperar.
echo.
echo  Se disser que o orcamento do dia acabou, e mesmo isso: sao 200
echo  mil tokens por dia e recomeca amanha. O que ja tinha sido lido
echo  fica guardado.
echo.
pause
echo.
"%PY%" radar.py --ler-pecas tudo
echo.
pause

