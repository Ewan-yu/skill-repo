@echo off
chcp 65001 >/dev/null 2>&1
set PYTHONIOENCODING=utf-8
python "%~dp0mx_data.py" %*
