@echo off
title Sistema de Perforacion - Report_Perforacion
color 0A

echo.
echo  =====================================================
echo   SISTEMA DE PERFORACION  ^|  Report_Perforacion
echo   Puerto: 8501  ^|  http://localhost:8501
echo  =====================================================
echo.

:: Verificar que el directorio del proyecto existe
if not exist "%~dp0app_perforacion.py" (
    color 0C
    echo  [ERROR] No se encontro app_perforacion.py en:
    echo          %~dp0
    echo.
    echo  Verifica que este lanzador este dentro del directorio correcto.
    pause
    exit /b 1
)

:: Verificar que el entorno virtual existe
if not exist "%~dp0.venv\Scripts\activate.bat" (
    color 0C
    echo  [ERROR] No se encontro el entorno virtual en:
    echo          %~dp0.venv\
    echo.
    echo  Para crearlo, ejecuta en PowerShell:
    echo    cd "%~dp0"
    echo    python -m venv .venv
    echo    .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: Verificar que streamlit está instalado en el venv
if not exist "%~dp0.venv\Scripts\streamlit.exe" (
    color 0C
    echo  [ERROR] Streamlit no esta instalado en el entorno virtual.
    echo.
    echo  Para instalarlo, ejecuta:
    echo    "%~dp0.venv\Scripts\pip.exe" install -r "%~dp0requirements.txt"
    echo.
    pause
    exit /b 1
)

echo  Activando entorno virtual...
call "%~dp0.venv\Scripts\activate.bat"

echo  Iniciando Streamlit en puerto 8501...
echo  Abre tu navegador en: http://localhost:8501
echo.
echo  Presiona Ctrl+C para detener el servidor.
echo.

"%~dp0.venv\Scripts\streamlit.exe" run "%~dp0app_perforacion.py" ^
    --server.port 8501 ^
    --server.headless false ^
    --browser.gatherUsageStats false

if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo  [ERROR] Streamlit termino con codigo de error %ERRORLEVEL%
    echo.
    echo  Posibles causas:
    echo    - Puerto 8501 ya en uso ^(otro proceso corriendo^)
    echo    - Dependencia faltante ^(revisa el mensaje de error arriba^)
    echo    - Error en app_perforacion.py
    echo.
)

pause
