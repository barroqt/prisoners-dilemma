from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import storage
from builder.compiler import (
    BuilderValidationError,
    compile_definition,
    describe_definition,
    render_python_source,
    validate_definition,
)
from core.match_history import match_history_with_noise_events, payoff
from simulation.jobs import JOB_MANAGER
from simulation.service import (
    available_strategies,
    available_strategies_meta,
    demo_match,
    resolve_players,
    run_simulation,
)


class SimulationRequest(BaseModel):
    strategies: list[str] = Field(min_length=2, max_length=64)
    rounds: int = Field(gt=0, le=5000)
    iterations: int = Field(gt=0, le=200)
    noise: float = Field(ge=0.0, le=1.0, default=0.0)


class BuilderDefinitionRequest(BaseModel):
    definition: dict


class BuilderTestRequest(BaseModel):
    definition: dict
    rounds: int = Field(gt=0, le=1000, default=100)


class SaveStrategyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=400)
    definition: dict


class PublishRequest(BaseModel):
    published: bool


app = FastAPI(title="Prisoner's Arena API")
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

SANDBOX_OPPONENTS = [
    "s01 - Always Coop",
    "s02 - Always Def",
    "s03 - Tit For Tat",
    "s04 - Grim Trigger",
    "s05 - Pavlov",
]


def _require_token(token: str | None) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Missing X-Anon-Token header.")
    return token


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/strategies")
def get_strategies() -> dict[str, list[str]]:
    return {"strategies": available_strategies()}


@app.get("/strategies/meta")
def get_strategies_meta() -> dict[str, list[dict]]:
    return {"strategies": [s.__dict__ for s in available_strategies_meta()]}


@app.get("/strategies/demo")
def get_strategy_demo(id: str, rounds: int = 24) -> dict:
    try:
        return demo_match(id, rounds=min(max(rounds, 4), 60))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Simulation: precompute-then-replay. /simulate/async + polling for large runs.
# ---------------------------------------------------------------------------

@app.post("/simulate")
def simulate(request: SimulationRequest) -> dict:
    try:
        result = run_simulation(
            strategies=request.strategies,
            rounds=request.rounds,
            iterations=request.iterations,
            noise=request.noise,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result_id = JOB_MANAGER.store_result(result)
    result["result_id"] = result_id
    return result


@app.post("/simulate/async")
def simulate_async(request: SimulationRequest) -> dict:
    try:
        # Validate strategy ids upfront so bad requests fail fast, not mid-job.
        resolve_players(request.strategies)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    def work(progress) -> dict:
        return run_simulation(
            strategies=request.strategies,
            rounds=request.rounds,
            iterations=request.iterations,
            noise=request.noise,
            progress=progress,
        )

    job = JOB_MANAGER.submit(work)
    return job.to_dict()


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = JOB_MANAGER.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job.")
    return job.to_dict()


@app.get("/results/{result_id}")
def get_result(result_id: str) -> dict:
    result = JOB_MANAGER.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown or expired result.")
    return result


# ---------------------------------------------------------------------------
# Research data export (CSV / JSON)
# ---------------------------------------------------------------------------

@app.get("/results/{result_id}/export")
def export_result(result_id: str, format: str = "json", dataset: str = "full") -> Response:
    result = JOB_MANAGER.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown or expired result.")

    if format == "json":
        return Response(
            content=json.dumps(result, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="arena_{result_id}.json"'},
        )
    if format != "csv":
        raise HTTPException(status_code=422, detail="format must be 'json' or 'csv'.")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if dataset == "leaderboard":
        columns = list(result["leaderboard"][0].keys())
        writer.writerow(columns)
        for row in result["leaderboard"]:
            writer.writerow([row.get(c) for c in columns])
    elif dataset == "matrix":
        names = result["matrix"]["names"]
        writer.writerow(["strategy"] + names)
        for name, row in zip(names, result["matrix"]["avg_scores"]):
            writer.writerow([name] + row)
    elif dataset == "rounds":
        early_end = result["config"]["phase_bounds"]["early_end"]
        mid_end = result["config"]["phase_bounds"]["mid_end"]
        writer.writerow(
            ["match_id", "p1", "p2", "round", "phase", "p1_move", "p2_move",
             "p1_score", "p2_score", "p1_noise_flip", "p2_noise_flip"]
        )
        for match in result["matches"]:
            noise_by_round = {(r, p) for r, p in match["noise_events"]}
            for i, (m1, m2) in enumerate(zip(match["moves_p1"], match["moves_p2"])):
                move1, move2 = m1 == "C", m2 == "C"
                score1, score2 = payoff[(move1, move2)]
                phase = "early" if i < early_end else "mid" if i < mid_end else "late"
                writer.writerow(
                    [match["id"], match["p1"], match["p2"], i + 1, phase, m1, m2,
                     score1, score2, int((i, 0) in noise_by_round), int((i, 1) in noise_by_round)]
                )
    else:
        raise HTTPException(status_code=422, detail="dataset must be leaderboard, matrix, or rounds.")

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="arena_{result_id}_{dataset}.csv"'},
    )


# ---------------------------------------------------------------------------
# Anonymous identity (no account required)
# ---------------------------------------------------------------------------

@app.post("/anon/session")
def anon_session() -> dict:
    return {"token": storage.issue_token()}


# ---------------------------------------------------------------------------
# No-code strategy builder
# ---------------------------------------------------------------------------

@app.post("/builder/compile")
def builder_compile(request: BuilderDefinitionRequest) -> dict:
    try:
        normalized = validate_definition(request.definition)
        return {
            "valid": True,
            "definition": normalized,
            "python_source": render_python_source(normalized),
            "description_lines": describe_definition(normalized),
        }
    except BuilderValidationError as exc:
        return JSONResponse(status_code=422, content={"valid": False, "error": str(exc)})


@app.post("/builder/test")
def builder_test(request: BuilderTestRequest) -> dict:
    try:
        strategy = compile_definition(request.definition)
    except BuilderValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    opponents, labels = resolve_players(SANDBOX_OPPONENTS)
    results = []
    total = 0
    for opponent_id, opponent_fn in opponents.items():
        history, _ = match_history_with_noise_events(strategy, opponent_fn, request.rounds, 0.0)
        my_score = sum(payoff[m][0] for m in history)
        opp_score = sum(payoff[m][1] for m in history)
        total += my_score
        results.append(
            {
                "opponent": labels[opponent_id],
                "my_score": my_score,
                "opponent_score": opp_score,
                "outcome": "win" if my_score > opp_score else "loss" if opp_score > my_score else "tie",
                "my_moves": "".join("C" if m[0] else "D" for m in history[:60]),
                "opponent_moves": "".join("C" if m[1] else "D" for m in history[:60]),
            }
        )
    return {"rounds": request.rounds, "total_score": total, "matches": results}


# ---------------------------------------------------------------------------
# Custom strategy persistence + marketplace
# ---------------------------------------------------------------------------

@app.get("/custom-strategies")
def list_custom(x_anon_token: str | None = Header(default=None)) -> dict:
    token = _require_token(x_anon_token)
    return {"strategies": storage.list_owned(token)}


@app.post("/custom-strategies")
def save_custom(request: SaveStrategyRequest, x_anon_token: str | None = Header(default=None)) -> dict:
    token = _require_token(x_anon_token)
    try:
        normalized = validate_definition(request.definition)
        source = render_python_source(normalized)
    except BuilderValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return storage.save_strategy(token, request.name, request.description, normalized, source)


@app.put("/custom-strategies/{strategy_id}")
def update_custom(
    strategy_id: str, request: SaveStrategyRequest, x_anon_token: str | None = Header(default=None)
) -> dict:
    token = _require_token(x_anon_token)
    try:
        normalized = validate_definition(request.definition)
        source = render_python_source(normalized)
    except BuilderValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    updated = storage.update_strategy(strategy_id, token, request.name, request.description, normalized, source)
    if updated is None:
        raise HTTPException(status_code=404, detail="Strategy not found or not yours.")
    return updated


@app.delete("/custom-strategies/{strategy_id}")
def delete_custom(strategy_id: str, x_anon_token: str | None = Header(default=None)) -> dict:
    token = _require_token(x_anon_token)
    if not storage.delete_strategy(strategy_id, token):
        raise HTTPException(status_code=404, detail="Strategy not found or not yours.")
    return {"deleted": strategy_id}


@app.post("/custom-strategies/{strategy_id}/publish")
def publish_custom(
    strategy_id: str, request: PublishRequest, x_anon_token: str | None = Header(default=None)
) -> dict:
    token = _require_token(x_anon_token)
    if not storage.set_published(strategy_id, token, request.published):
        raise HTTPException(status_code=404, detail="Strategy not found or not yours.")
    return {"id": strategy_id, "published": request.published}


@app.get("/marketplace")
def marketplace() -> dict:
    strategies = storage.list_published()
    for record in strategies:
        record["description_lines"] = describe_definition(record["definition"])
    return {"strategies": strategies}


@app.post("/marketplace/{strategy_id}/fork")
def fork(strategy_id: str, x_anon_token: str | None = Header(default=None)) -> dict:
    token = _require_token(x_anon_token)
    forked = storage.fork_strategy(strategy_id, token)
    if forked is None:
        raise HTTPException(status_code=404, detail="Strategy not found or not published.")
    return forked
