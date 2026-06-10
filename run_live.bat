@echo off
if "%~1"=="" (
    echo Error: Please provide a company domain.
    echo Example: run_live razorpay.com
    exit /b 1
)
python main.py %1 --dedup-days 0
