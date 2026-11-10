
@echo off

REM Go to the project directory
cd /d "%~dp0"

REM Run incremental ETL using the virtual environment
"%~dp0.venv\Scripts\python.exe" "%~dp0src\incremental_etl.py"

REM Return the Python execution status
exit /b %errorlevel%
