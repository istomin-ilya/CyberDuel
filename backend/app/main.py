from fastapi import FastAPI


app = FastAPI(
    title="CyberDuelApi",
    version="0.1.0"
)

# Health check endpoint
@app.get("/")
async def root():
    return {"message": "Hello World", "status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}