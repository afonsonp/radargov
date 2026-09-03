@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat"
echo.
echo  LER O DETALHE DE TODOS OS ANUNCIOS
echo.
echo  Vai buscar o CPV, o prazo, o preco base, a plataforma e o texto
echo  de todos os anuncios que ainda nao os tem. A rotina diaria le so
echo  os ultimos 60 dias, e sem detalhe um anuncio nao aparece num
echo  filtro por CPV, nem na arvore, nem nos indicadores: esta na base
echo  e e como se nao estivesse.
echo.
echo  DEMORA CERCA DE 24 HORAS. E um pedido por segundo, de proposito,
echo  para nao castigar o portal do Diario da Republica.
echo.
echo  Nao gasta tokens nem dinheiro: e so ir buscar paginas. O que
echo  gasta modelo e o ensaio.bat / --ler-pecas.
echo.
echo  Deixa esta janela a correr e esquece. Podes fecha-la, dar Ctrl-C
echo  ou desligar o computador: nao perdes nada -- cada anuncio fica
echo  gravado assim que e lido, e voltar a correr isto continua de
echo  onde ia. Se a rede falhar, espera 30 segundos e tenta outra vez.
echo.
pause
echo.
"%PY%" radar.py --detalhes tudo
echo.
pause
