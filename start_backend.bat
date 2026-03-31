@echo off
echo Starting CrisisIQ Backend...
python -m uvicorn main:app --reload
pause
