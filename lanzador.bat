@echo off
title Sistema Reporte de Perforaci?n
color 0A
setlocal EnableExtensions

echo ==========================================
echo   SISTEMA REPORTE DE PERFORACION
echo ==========================================
echo.

cd /d "C:\Python_Proyectos\Report_Perforacion" || (
    echo [ERROR] No se pudo abrir la carpeta del proyecto.
    pause
    exit /b 1
)

echo [INFO] Carpeta del proyecto: %cd%
echo.

if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activando entorno virtual...
    call "venv\Scripts\activate.bat"
) else (
    echo [WARN] No se encontro venv. Se usara el Python del sistema.
)

echo.
echo [INFO] Verificando Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python no esta disponible.
    echo [INFO] Instala Python o activa el entorno virtual.
    pause
    exit /b 1
)

echo.
echo [INFO] Verificando Streamlit...
python -m streamlit --version
if errorlevel 1 (
    echo [ERROR] Streamlit no esta instalado.
    echo [INFO] Instala con: pip install streamlit
    pause
    exit /b 1
)

echo.
echo [INFO] Iniciando sistema...
echo.
python -m streamlit run app_perforacion.py
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo [ERROR] Streamlit finalizo con codigo %EXITCODE%.
)

echo.
echo [INFO] La ventana permanecera abierta.
pause
exit /b %EXITCODE%
