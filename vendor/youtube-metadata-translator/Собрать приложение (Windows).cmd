@echo off
setlocal
echo Сборка единого exe (нужен pip install pyinstaller)...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "YouTube Metadata Translator" --icon "webui_static\app_icon.ico" --add-data "webui_static;webui_static" webui.py
echo.
echo Готово: dist\YouTube Metadata Translator.exe
pause
