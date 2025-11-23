import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

from Server.AppCore import AppCore, Position, FundingStats
from Server.ServiceManager.MicroserviceManager import Microservice
from Server.AssetReporter.AssetReporter import AssetReporter

app = FastAPI()

# CORS for development (React dev server on 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app_core = AppCore()
asset_reporter = AssetReporter()

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


@app.get("/bot1api/positions", response_model=List[Position])
def get_positions():
    return app_core.get_positions()


@app.get("/bot1api/funding", response_model=List[FundingStats])
def get_funding(quick: bool = False):
    try:
        return app_core.get_funding_stats(quick=quick)
    except Exception as e:
        print(f"[WARN] /bot1api/funding failed: {e}")
        # Return empty list so UI doesn’t break; details in server log
        return []

class PositionPayLoad(BaseModel):
    symbol: str
    size: float

@app.post("/bot1api/positions/open")
def update_position_status(payload: PositionPayLoad):
    result, e = app_core.open_position(payload.symbol, payload.size)
    if not result:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": f"Position on {payload.symbol} opened"}


@app.post("/bot1api/positions/estimate")
def estimate_position_status(payload: PositionPayLoad):
    result, e = app_core.estimate_position(payload.symbol, payload.size)
    if not result:
        raise HTTPException(status_code=400, detail=str(e))
    return e


# New: open hedge position with explicit long/short selection
class HedgeOpenPayload(BaseModel):
    symbol: str
    longExchange: str
    longContracts: float
    shortExchange: str
    shortContracts: float

@app.post("/bot1api/positions/open-hedge")
def open_position_hedge(payload: HedgeOpenPayload):
    ok, res = app_core.open_position_hedge(
        payload.symbol,
        payload.longExchange,
        payload.longContracts,
        payload.shortExchange,
        payload.shortContracts,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=str(res))
    return res


class AssetRecord(BaseModel):
    timestamp: str
    side1: float
    side2: float
    total: float

# Model mới cho current asset (có cộng thêm lượng đang transfer)
class AssetCurrentRecord(BaseModel):
    timestamp: str
    side1: float
    side2: float
    total: float
    transfer_inflight: float
    total_with_transfer: float

@app.get("/bot1api/asset-report", response_model=List[AssetRecord])
def get_asset_report(limit: Optional[int] = None):
    data = asset_reporter.get_report(limit=limit)
    # FastAPI sẽ validate theo model
    return data

# Updated: get current live balances với transfer_inflight
@app.get("/bot1api/asset-report/current", response_model=AssetCurrentRecord)
def get_asset_current():
    data = asset_reporter.get_current()
    return data

@app.post("/bot1api/asset-report/snapshot", response_model=AssetRecord)
def create_asset_snapshot():
    data = asset_reporter.take_snapshot()
    return data

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
