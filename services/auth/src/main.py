from fastapi import FastAPI
from src.routes import auth
from src.config import get_settings

settings = get_settings()
app = FastAPI(title="Auth Service")

app.include_router(auth.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def home():
    return {"message": "It is home"}

def main():
    import uvicorn
    uvicorn.run("src.main:app", host=settings.AUTH_DB_HOST, port=settings.AUTH_PORT, reload=True)

if __name__ == "__main__":
    main()