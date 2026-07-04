"""Live API QA against the running server."""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8123"
issues = []


def req(method, path, body=None, token=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("X-Anon-Token", token)
    try:
        with urllib.request.urlopen(r) as resp:
            payload = resp.read()
            return resp.status, payload if raw else json.loads(payload)
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload)
        except Exception:
            return e.code, payload.decode(errors="replace")


def check(name, cond, detail=""):
    status = "ok " if cond else "FAIL"
    print(f"[{status}] {name} {detail if not cond else ''}")
    if not cond:
        issues.append(f"{name}: {detail}")


# 1. sync simulate
s, d = req("POST", "/simulate", {"strategies": ["s03 - Tit For Tat", "s02 - Always Def", "s01 - Always Coop"], "rounds": 50, "iterations": 2, "noise": 0})
check("simulate sync 200", s == 200, d)
check("simulate has result_id", isinstance(d, dict) and "result_id" in d)
rid = d["result_id"]

# TFT invariant on served match data
for m in d["matches"]:
    for seat, me, opp in ((1, "moves_p1", "moves_p2"), (2, "moves_p2", "moves_p1")):
        who = m["p1"] if seat == 1 else m["p2"]
        if who != "s03 - Tit For Tat":
            continue
        mine, theirs = m[me], m[opp]
        bad = [i for i in range(len(mine)) if mine[i] != ("C" if i == 0 else theirs[i - 1])]
        check(f"TFT invariant in served match vs {m['p1'] if seat==2 else m['p2']}", not bad, f"bad rounds {bad[:5]}")

# 2. exports
for fmt, ds in [("json", "full"), ("csv", "rounds"), ("csv", "leaderboard"), ("csv", "matrix")]:
    s, payload = req("GET", f"/results/{rid}/export?format={fmt}&dataset={ds}", raw=True)
    check(f"export {fmt}/{ds}", s == 200 and len(payload) > 50, f"status {s} len {len(payload)}")

# bad export params
s, d2 = req("GET", f"/results/{rid}/export?format=xml")
check("export bad format 422", s == 422, s)
s, d2 = req("GET", f"/results/{rid}/export?format=csv&dataset=bogus")
check("export bad dataset 422", s == 422, s)

# 3. async job flow
s, job = req("POST", "/simulate/async", {"strategies": ["s03 - Tit For Tat", "s05 - Pavlov"], "rounds": 100, "iterations": 1, "noise": 0.05})
check("async submit", s == 200 and job.get("job_id"), job)
for _ in range(50):
    s, info = req("GET", f"/jobs/{job['job_id']}")
    if info["status"] in ("done", "error"):
        break
    time.sleep(0.1)
check("async done", info["status"] == "done", info)
s, res = req("GET", f"/results/{info['result_id']}")
check("async result fetch", s == 200 and res["config"]["rounds"] == 100)

# unknown strategy fails fast
s, d2 = req("POST", "/simulate/async", {"strategies": ["s03 - Tit For Tat", "nope"], "rounds": 10, "iterations": 1})
check("async unknown strategy 422", s == 422, (s, d2))

# 4. demo endpoint
s, demo = req("GET", "/strategies/demo?id=" + urllib.request.quote("s04 - Grim Trigger"))
check("demo grim", s == 200 and len(demo["moves"]) == 24, (s, demo if s != 200 else ""))
s, d2 = req("GET", "/strategies/demo?id=bogus")
check("demo unknown 404", s == 404, s)

# 5. anon session + builder CRUD
s, tok = req("POST", "/anon/session")
check("anon session", s == 200 and len(tok["token"]) == 32, tok)
token = tok["token"]

tft_def = {"first_move": "cooperate",
           "rules": [{"conditions": [{"fact": "opp_last_move", "op": "is", "value": "defect"}], "action": {"type": "defect"}}],
           "default_action": {"type": "cooperate"}}

s, comp = req("POST", "/builder/compile", {"definition": tft_def})
check("builder compile", s == 200 and comp["valid"], comp)
s, bad = req("POST", "/builder/compile", {"definition": {"rules": [{"conditions": [], "action": "defect"}]}})
check("builder compile invalid 422", s == 422 and bad["valid"] is False, (s, bad))

s, test = req("POST", "/builder/test", {"definition": tft_def, "rounds": 100})
check("builder test", s == 200 and len(test["matches"]) == 5, (s, test if s != 200 else ""))

s, saved = req("POST", "/custom-strategies", {"name": "QA TFT", "description": "qa", "definition": tft_def}, token=token)
check("save custom", s == 200 and saved["id"].startswith("custom:"), (s, saved))
cid = saved["id"]

s, d2 = req("GET", "/custom-strategies", token=token)
check("list mine", s == 200 and any(x["id"] == cid for x in d2["strategies"]))

s, d2 = req("POST", "/custom-strategies", {"name": "x", "definition": tft_def})
check("save without token 401", s == 401, s)

# custom strategy fights in a tournament
s, d2 = req("POST", "/simulate", {"strategies": [cid, "s02 - Always Def", "s03 - Tit For Tat"], "rounds": 60, "iterations": 1})
check("simulate with custom", s == 200, d2 if s != 200 else "")
if s == 200:
    m = next(mm for mm in d2["matches"] if {mm["p1"], mm["p2"]} == {cid, "s03 - Tit For Tat"})
    check("custom TFT vs TFT all-coop", set(m["moves_p1"]) == {"C"} and set(m["moves_p2"]) == {"C"}, m)

# demo with custom id
s, demo = req("GET", "/strategies/demo?id=" + urllib.request.quote(cid))
check("demo custom", s == 200, (s, demo))

# update / publish / marketplace / fork / delete
s, upd = req("PUT", f"/custom-strategies/{cid}", {"name": "QA TFT v2", "description": "qa2", "definition": tft_def}, token=token)
check("update custom", s == 200 and upd["name"] == "QA TFT v2", (s, upd))
s, d2 = req("PUT", f"/custom-strategies/{cid}", {"name": "steal", "definition": tft_def}, token="0" * 32)
check("update wrong token 404", s == 404, s)

s, d2 = req("POST", f"/custom-strategies/{cid}/publish", {"published": True}, token=token)
check("publish", s == 200 and d2["published"] is True, (s, d2))
s, market = req("GET", "/marketplace")
check("marketplace lists it", s == 200 and any(x["id"] == cid for x in market["strategies"]), (s, market))

s, tok2 = req("POST", "/anon/session")
s, forked = req("POST", f"/marketplace/{cid}/fork", {}, token=tok2["token"])
check("fork", s == 200 and forked["forked_from"] == cid, (s, forked))

s, d2 = req("DELETE", f"/custom-strategies/{forked['id']}", token=tok2["token"])
check("delete fork", s == 200, (s, d2))
s, d2 = req("DELETE", f"/custom-strategies/{cid}", token=token)
check("delete original", s == 200, (s, d2))
s, market = req("GET", "/marketplace")
check("marketplace empty of it", not any(x["id"] == cid for x in market["strategies"]))

# 6. edge: simulate rounds bounds
s, d2 = req("POST", "/simulate", {"strategies": ["s01 - Always Coop", "s02 - Always Def"], "rounds": 5001, "iterations": 1})
check("rounds cap 422", s == 422, s)

print()
print("ISSUES:", len(issues))
for i in issues:
    print(" -", i)
