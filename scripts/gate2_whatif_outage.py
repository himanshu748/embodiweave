import json, subprocess, time
from ew import service, whatif, records
from ew.graph import db
from ew.graph.db import GraphUnavailable

req = {**service.target_request(budget=60_000), "candidate_run_kinds": ["library"]}
d = service.record_decision(req)
print("PRODUCTION (library catalog)", d["id"], "rev", d["graph_revision"], "->", d["selected"], "|", d["explanation"])
for c in d["ranking"]:
    print(f"   #{c['rank']} {c['policy_id']:12s} p={c['p_reach']:.3f} {c['p_basis']} val={c['validation']['score']:+.3f}")
before = whatif.fingerprint()
wg = whatif.create()
for _ in range(2):
    whatif.add_hypothetical_trial(wg, "P-cross-a", req["target_family_id"], req["contract"], req["threshold_id"],
                                  req["recipe"], req["budget"], reached=True, steps_to_threshold=45_000)
dw = service.record_decision(req, mode="what-if", graph=wg)
print("WHAT-IF", wg, dw["id"], "rev", dw["graph_revision"], "->", dw["selected"], "|", dw["explanation"])
for c in dw["ranking"]:
    print(f"   #{c['rank']} {c['policy_id']:12s} p={c['p_reach']:.3f} {c['p_basis']} val={c['validation']['score']:+.3f}")
wg2 = whatif.create()
whatif.set_hypothetical_contract(wg2, "P-static-a", "ew-contract-1m:6fad9cbfe838")
dw2 = service.record_decision(req, mode="what-if", graph=wg2)
print("WHAT-IF compat", wg2, "->", dw2["selected"], "rejected:", [(r["policy_id"], r["reasons"][0][:60]) for r in dw2["rejected"]])
after = whatif.fingerprint()
# production graph only gains nothing from what-if work
print("production fingerprint unchanged:", before == after, before["revision"], after["revision"])
try:
    whatif.add_hypothetical_trial("ew", "P-cross-a", "x", "y", "z", "r", 1, True, 1)
except PermissionError as e:
    print("write to production refused:", e)
whatif.drop(wg); whatif.drop(wg2)

print("\nOUTAGE TEST: stopping FalkorDB container")
subprocess.run(["docker", "stop", "falkordb"], check=True, capture_output=True)
t0 = time.time()
try:
    service.record_decision(req)
    print("UNEXPECTED: decision succeeded without graph")
except GraphUnavailable as e:
    print(f"decision stopped explicitly after {time.time()-t0:.2f}s:", e)
n = len(records.all_of("decision"))
print("recorded evidence still readable offline (Recorded mode):", n, "decision records")
subprocess.run(["docker", "start", "falkordb"], check=True, capture_output=True)
for _ in range(30):
    if db.ping(): break
    time.sleep(0.5)
print("graph back, revision", db.revision())
