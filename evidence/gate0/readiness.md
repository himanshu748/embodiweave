# Gate 0: readiness record

Recorded 2026-10-15 09:20 IST (03:50 UTC) by the build session.

## Clock
`TZ=Asia/Kolkata date` -> Thu Oct 15 09:19:54 IST 2026 (after the 15 Oct 00:01 IST opening).

## Official rules (fetched 2026-10-15 from https://www.wemakedevs.org/hackathons/falkordb/rules)
- Rule 7: "The hackathon runs from October 15, 12:01 AM IST to October 18, 11:59 PM IST."
- Rule 8: "The main coding and design work must begin after the hackathon starts." / "You may discuss ideas, create notes, sketch the graph model, or prepare diagrams beforehand."
- Rule 2/3: FalkorDB must be the primary graph database and support a central part of the product.
- Rule 10: public repo, README with setup and graph model, Cypher queries, demo video, live deploy or full local setup, track.
- Rule 11/13: AI coding assistants allowed but must be disclosed.
- Rule 6: public, synthetic or own data only.

## Pre-event material (disclosed, not backdated)
`docs/v2-original/prd.md` and `docs/v2-original/spec.md` are dated 14 October 2026 (before opening).
They are written requirements documents and contain no code. Whether a written PRD/spec counts as
"notes" or as "design work" under Rule 8 is the organizers' call; we disclose them with their real date
rather than relabel them. All source code in this repository was written after opening.
sha256 prd.md  6765cc9e41d6f56f7a5f5483359b743a913461db10afb5f663e4d8792461feaa
sha256 spec.md b67c5b8ab48de17545f94ba05bef195afa71cc8917a2970ac130dc7569a4d0e4

## Execution host (observed, not the user's Mac)
- Claude Code cloud container: Linux 6.18 x86_64, Ubuntu 24.04, 4 CPUs, 15.7 GiB RAM, no GPU, ~30 GB writable.
- Working dir /home/claude/embodiweave; durable mirror /mnt/project-files/embodiweave (network mount).
- Python 3.13.16 in a venv. Docker client 29.8.2; daemon started in-container (dockerd 29.8.2, overlayfs).
- Network: PyPI and Docker Hub reachable; download.pytorch.org and wemakedevs.org blocked for curl (rules read via fetch tool).
- The MacBook Air M4 is not reachable from this session and nothing here was run on it.

## FalkorDB runtime
- Image `falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6` (created 2026-10-08), graph module ver 60002.
- `GRAPH.RO_QUERY t "CREATE (:X {a:2})"` -> error "graph.RO_QUERY is to be executed only on read-only queries"; count stayed 1.
- `GRAPH.COPY t t_copy` -> OK, copy readable (candidate What-if isolation mechanism).
- Default module args: TIMEOUT 1000 ms, RESULTSET_SIZE 10000.

## Runtime LLM
No runtime LLM API credential present in the environment (only the coding assistant's own session).
Gate 3 live-agent test is blocked until the user supplies one. AWS credentials exist but using Bedrock would spend money: not used without approval.
