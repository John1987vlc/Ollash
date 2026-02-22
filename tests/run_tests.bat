@echo off
REM Run comprehensive test suite for Ollash Cowork improvements

REM Ensure we're running from the project root
cd /d "%~dp0\.."

cls
echo.
echo ==========================================
echo Ollash Test Suite - Cowork Improvements
echo ==========================================
echo.

REM Check if pytest is installed
python -m pytest --version > nul 2>&1
if errorlevel 1 (
    echo Installing pytest and dependencies...
    pip install -q pytest pytest-mock pytest-cov
)

echo Running unit tests...
echo.

REM Run tests with coverage
python -m pytest tests/unit/ ^
    -v ^
    --tb=short ^
    --cov=src ^
    --cov-report=term-missing ^
    --cov-report=html ^
    -m "unit"

if errorlevel 1 (
    echo.
    echo ==========================================
    echo ✗ Some tests failed!
    echo ==========================================
    exit /b 1
)

echo.
echo ==========================================
echo ✓ All tests passed!
echo.
echo Coverage report generated in htmlcov\index.html
echo ==========================================
