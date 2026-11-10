@echo off
setlocal
cd /d "D:\FUNDSHOT\weex_alerts"
if not exist ".venv_weex_live\Scripts\python.exe" exit /b 11
".venv_weex_live\Scripts\python.exe" -B "weex_supervised_process_monitor_v6.py" --iterations 1 --interval 2
exit /b %ERRORLEVEL%
