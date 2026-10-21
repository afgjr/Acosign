"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api import router as api_router

app = FastAPI(
    title="AudioSignature API",
    description="Acoustic fingerprinting and cryptographic provenance engine",
    version="0.1.0",
)

# Mount API endpoints
app.include_router(api_router)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "AudioSignature Engine",
        "environment": "INSA Capstone Development",
    }
