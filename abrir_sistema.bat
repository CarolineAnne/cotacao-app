@echo off
setlocal

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo.
    echo Execute estes comandos antes de abrir o sistema:
    echo python -m venv venv
    echo venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

"venv\Scripts\python.exe" -m streamlit run app.py

echo.
echo O sistema foi encerrado.
pause
