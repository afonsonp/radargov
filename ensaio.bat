@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ENSAIO DE LEITURA
echo  Poe o que o modelo escreveu ao lado do texto do documento.
echo.
set /p REF=" Referencia do concurso (ex: 21295/2026): "
if "%REF%"=="" goto fim
echo.
python ".claude\skills\ensaio-de-leitura\ensaio.py" %REF% --sem-modelo
echo.
echo  ----------------------------------------------------------------
echo   V literal: a frase esta no documento tal e qual.
echo   ~ reescrito: as palavras estao la, mas nao seguidas. Normal.
echo   ? sem apoio: ha termos que nao aparecem. Olha para a janela ao
echo     lado antes de dar por errado -- costuma ser o modelo a dizer
echo     "Automatizacao" onde o documento diz "Automatizar".
echo  ----------------------------------------------------------------
:fim
echo.
pause
