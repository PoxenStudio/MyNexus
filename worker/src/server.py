import uvicorn
from fastapi import FastAPI

from config import load_config
from pipelines.ingestion import build_status

app = FastAPI(title="MyNexus Worker")


@app.get("/health")
@app.get("/internal/health")
def health():
    return {"status": "ok", "service": "worker"}


@app.get("/internal/pipeline")
def pipeline_status():
    return build_status()


def main():
    cfg = load_config()
    print(f"worker listening on :{cfg.port}")
    uvicorn.run(app, host="0.0.0.0", port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
