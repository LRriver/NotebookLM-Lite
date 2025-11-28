from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import routes
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="NotebookLM-Lite API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
