from fastapi import FastAPI

app = FastAPI(
    title="AudioSignature API",
    description="Acoustic fingerprinting and cryptographic provenance engine",
    version="0.1.0"
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "AudioSignature Engine",
        "environment": "INSA Capstone Development"
    }
