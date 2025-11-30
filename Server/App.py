import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

from Server.ServiceManager.MicroserviceManager import Microservice

app = FastAPI()

# CORS for development (React dev server on 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app_core = AppCore()

@app.get("/bot1api/microservices", response_model=List[Microservice])
def get_microservices():
    return app_core.get_microservices()

class StatusUpdate(BaseModel):
    status: str  # "start" or "stop"

@app.put("/bot1api/microservices/{id}/start")
def update_microservice_status(id: str):
    if app_core.start_microservice(id):
        return {"message": f"{id} started"}
    raise HTTPException(status_code=404, detail="Microservice not found")

@app.put("/bot1api/microservices/{id}/stop")
def update_microservice_status(id: str):
    if app_core.stop_microservice(id):
        return {"message": f"{id} stopped"}
    raise HTTPException(status_code=404, detail="Microservice not found")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    # Configurable host/port and optional SSL via environment variables
    host = os.environ.get("UVICORN_HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("UVICORN_PORT", "8000"))
    except ValueError:
        port = 8000

    reload_flag = os.environ.get("UVICORN_RELOAD", "true").lower() in ("1", "true", "yes")

    ssl_certfile = os.environ.get("UVICORN_SSL_CERTFILE")
    ssl_keyfile = os.environ.get("UVICORN_SSL_KEYFILE")
    ssl_keyfile_password = os.environ.get("UVICORN_SSL_KEYFILE_PASSWORD")

    # If cert/key are provided and exist, enable HTTPS
    ssl_kwargs = {}
    if ssl_certfile and ssl_keyfile and os.path.exists(ssl_certfile) and os.path.exists(ssl_keyfile):
        ssl_kwargs = {
            "ssl_certfile": ssl_certfile,
            "ssl_keyfile": ssl_keyfile,
            "ssl_keyfile_password": ssl_keyfile_password,
        }
        print(f"[INFO] Starting Uvicorn with HTTPS on {host}:{port}")
    else:
        print(f"[INFO] Starting Uvicorn without SSL on {host}:{port}")

    # Pass the app instance directly to avoid import path issues
    uvicorn.run(app, host=host, port=port, reload=reload_flag, **ssl_kwargs)
