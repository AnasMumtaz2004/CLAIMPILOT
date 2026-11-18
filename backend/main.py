from dotenv import load_dotenv


load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth
from routes import claims
from routes import decisions
from routes import documents
from routes import staff

app = FastAPI(title="InsureFlow")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(documents.router)
app.include_router(staff.router)
app.include_router(decisions.router)


@app.get("/health")
def health():
    """Return a simple health check."""
    return {"status": "ok"}