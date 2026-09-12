@echo off
setlocal
python -m pip install -r requirements.txt
if "%KENGURU_ADMIN_PASSWORD%"=="" set KENGURU_ADMIN_PASSWORD=CHANGE-THIS-PASSWORD
python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
