from fastapi import FastAPI
from sqlalchemy import text

from app.core.database import engine
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Research Copilot API",
    description="Backend API for the AI Research Copilot",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)

@app.get("/")
def root():
    return {
        "message": "AI Research Copilot API is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }


@app.get("/database-test")
def database_test():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT current_database()"))
            database_name = result.scalar()

        return {
            "status": "connected",
            "database": database_name,
        }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }