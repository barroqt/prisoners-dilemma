from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from simulation.service import available_strategies, available_strategies_meta, run_simulation


class SimulationRequest(BaseModel):
    strategies: list[str] = Field(min_length=1, max_length=41)
    rounds: int = Field(gt=0, le=5000)
    iterations: int = Field(gt=0, le=200)
    noise: float = Field(ge=0.0, le=1.0, default=0.0)


app = FastAPI(title="Prisoner's Dilemma Simulator API")
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/strategies")
def get_strategies() -> dict[str, list[str]]:
    return {"strategies": available_strategies()}


@app.get("/strategies/meta")
def get_strategies_meta() -> dict[str, list[dict]]:
    return {"strategies": [s.__dict__ for s in available_strategies_meta()]}


@app.post("/simulate")
def simulate(request: SimulationRequest) -> dict:
    result = run_simulation(
        strategies=request.strategies,
        rounds=request.rounds,
        iterations=request.iterations,
        noise=request.noise,
    )
    return result.to_dict()
