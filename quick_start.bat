@echo off
REM RiskSafeAI Quick Start Script (Windows)
REM This script sets up and runs RiskSafeAI locally

echo =========================================
echo    RiskSafeAI Local Setup
echo =========================================
echo.

REM Check if .env exists
if not exist .env (
    echo ❌ .env file not found!
    echo Please copy .env.example to .env and add your API keys:
    echo    copy .env.example .env
    echo    Edit .env and add: OPENAI_API_KEY, PINECONE_API_KEY, TAVILY_API_KEY
    exit /b 1
)

echo ✅ .env file found

REM Check if virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment exists
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo =========================================
echo    Testing Pinecone Connection
echo =========================================
echo.

REM Test Pinecone
python -c "import os; from dotenv import load_dotenv; from pinecone import Pinecone; load_dotenv(); pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY')); index = pc.Index('asic-compliance-rag'); stats = index.describe_index_stats(); print(f'✅ Pinecone connected!'); print(f'   Index: asic-compliance-rag'); print(f'   Vectors: {stats.total_vector_count:,}'); print(f'   Dimension: {stats.dimension}')"

if errorlevel 1 (
    echo ❌ Pinecone connection failed!
    echo Please check your PINECONE_API_KEY in .env file
    pause
    exit /b 1
)

echo.
echo =========================================
echo    Starting RiskSafeAI Server
echo =========================================
echo.
echo Server will start at: http://localhost:8000
echo.
echo Test with:
echo   curl http://localhost:8000/health
echo.
echo Or generate obligation register:
echo   curl -X POST http://localhost:8000/react/obligation_register ^
echo     -H "Content-Type: application/json" ^
echo     -d "{\"query\": \"Generate obligation register for fintech personal loans\"}"
echo.
echo Press CTRL+C to stop the server
echo.

REM Run server
python main.py

pause
