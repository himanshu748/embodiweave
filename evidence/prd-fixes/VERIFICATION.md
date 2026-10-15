# PRD acceptance revision, 15 October 2026

Base reviewed: `07d057f530229dd23b2b1cd51bf52e6ce490d3be`. The independent review reproduced queue,
validation, export and macOS installation defects. Original experiment records and model artifacts are preserved.

## Checks performed

| Area | Verification |
|---|---|
| Portable setup | Fresh Python 3.13 arm64 macOS venv installed the dependency lock; CUDA-only pins removed; missing provider HTTP dependencies now pinned |
| Queue and quota | Concurrent identical submissions create one job; competing reservations respect quota; 150k reserves 151,552; one worker lease; one training job per opted-in agent session |
| Crash and cancel | Queued cancellation writes Trial; running cancellation, interrupted recovery and existing immutable outcomes retained; unknown failed work keeps full quota reservation |
| Complete validation | Full canonical seeds/version/role/family/contract and summary consistency required; one-episode smoke evidence cannot rank or promote |
| Export | ZIP checksums verified; separate process executes embedded source CLI and matches saved-artifact evaluation; source revision and hashes included |
| Agent UI | Consent, explicit provider opt-in, loopback restriction, worker requirement, 12-turn cap, one training job and duplicate-session checks; public launch disabled |
| Full local suite | `EW_FALKOR_PORT=16379 ../prd-audit-venv/bin/python -m pytest -q`; see `pytest.txt` |
| Fresh launcher | Started empty `ew_local_accept` graph using the documented script, isolated artifact directory and pinned database. API returned graph up, worker alive, hosted_readonly=false before the test process exited |
| Browser | Landing, judge guide and studio: document width equals viewport at 360, 768 and 1440px; no horizontal document overflow |
| Replay | Actual replay advances; explicit still mode follows the same reduced-motion branch and shows final step 112; top-view toggle works |
| Live graph | Parent query returned 27 actual trial rows through GRAPH.RO_QUERY; scratch query returned 12; parameters and revision visible |
| What-if | Browser execution selected P-open-a after hypothetical trials; production fingerprint unchanged (rev 2); sandbox dropped and training disabled |
| Film | Actual browser captures, including simulator frames, live query responses, recorded ranking/gate and agent trace UI; edited captions/pointer; no new training depicted |

The PRD’s required implementation paths are now covered by executable tests and the provided interfaces.
The public demo intentionally remains read-only for heavy work. A new paid provider call was not made in
this acceptance revision: launcher safeguards are tested with a mocked process and the existing real
Sonnet MCP run provides the recorded runtime evidence. Benchmark experiments were not rerun or cherry-picked.

## Reproduction and historical provenance

New `repro-v2` exports contain Python source, source metadata, dependency lock and payload checksums.
The two historical bundles remain unchanged because recorded traces cite their old hashes. Training
source was not captured for those historical policies; the new exports explicitly label it unknown.
New training manifests record source identity. The recorded checkpoint’s new-format bundle was also extracted and evaluated from its own embedded source on all 60 val-target-v1 seeds. Every episode outcome and step count matched the original record, with 0.8667 success and 0.1333 collision. All payload checksums and source hashes matched (`export-verification.json`).

Saved-artifact evaluation is reproducible; bitwise identical
retraining across different hardware is not promised.

## Remaining limitations

Software simulation, a small checkpoint library and three seeds per benchmark arm. No arm cleared the
full test threshold; the featured checkpoint was rejected. No demonstrated efficiency or physical safety
claim. Eligibility of disclosed pre-event planning documents remains the organizer’s judgment.

The owner’s Render CLI confirmed service `srv-db88bfhsrm7s73dp7aeg` remains on the free plan. The final deployment identity and endpoint checks are supplied in the release receipt alongside this revision.
