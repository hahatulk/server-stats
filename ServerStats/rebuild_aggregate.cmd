@echo off
cd /d "%~dp0"
py.exe "@Resources\Aggregate\generate.py" --refresh
if errorlevel 1 (
  echo Generation failed. Install Python 3.9+ with Python Launcher or check servers.json.
  pause
)
