@echo off
rem YTD Texture Editor - double-click to run, or drop a .ytd file on this shortcut
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py" %*
