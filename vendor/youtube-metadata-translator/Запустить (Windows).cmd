@echo off
setlocal
python "%~dp0yt_metadata_translator.py"
if errorlevel 1 pause
