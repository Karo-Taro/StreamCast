@echo off
setlocal
rem pythonw = запуск без чёрного окна консоли (закрытие — кнопка в меню)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0webui.py"
    exit /b
)
python "%~dp0webui.py"
if errorlevel 1 pause
