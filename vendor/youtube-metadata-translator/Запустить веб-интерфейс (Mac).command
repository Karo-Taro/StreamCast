#!/bin/bash
cd "$(dirname "$0")"
python3 webui.py || { echo; read -p "Программа завершилась с ошибкой. Нажми Enter, чтобы закрыть окно..."; }
