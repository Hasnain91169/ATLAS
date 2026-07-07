# Case study: integrating a black-box multi-agent simulator

How ATLAS's `predict audience` feature came to drive
[MiroFish](https://github.com/666ghj/MiroFish) — an open-source, self-hosted swarm
simulator that ships **no API documentation** — reliably enough to put behind a CLI
command with a test suite.

## The goal

ATLAS plans and drafts, but never tested how the *outside world* would receive its
output. MiroFish simulates collective social reaction to a seed event using
thousands of persona agents. If ATLAS could seed it with an announcement and read
back a reaction, it would gain a "rehearse before you go public" capability. The
catch: MiroFish is a heavyweight local app (Flask + Node + Docker + Zep memory),
and its HTTP surface is undocumented.

## 1. Building against an API that doesn't exist yet

The first client was written from MiroFish's marketing description, assuming a
hosted `POST /v1/simulate` that returns `{verdict, risk_score}` synchronously. That
was **wrong in every dimension** — but writing it forced the right abstraction:

- A `PredictionClient` interface with two implementations: a real client and a
  `StubPredictionClient` that returns deterministic output offline. This meant the
  entire feature — CLI, storage, verdict classification, tests — could be built and
  shipped *before the real API was understood*, and kept working afterward.

## 2. Discovering the real contract by reading the source

MiroFish turned out to be self-hosted (`localhost:5001`, no auth), so the honest
move was to read its Flask blueprints (`backend/app/api/{graph,simulation,report}.py`)
rather than guess. Three things fell out:

1. **It's not one call — it's a 6-stage async pipeline.** A single prediction means:
   `ontology/generate` → `graph/build` → `simulation/create` → `prepare` →
   `start` + `run-status` → `report/generate`, where every long stage returns a
   `task_id` you poll to completion.
2. **Every response is enveloped:** `{"success": bool, "data": {...}}`. The initial
   client read fields at the top level, so stage 1 failed with *"ontology response
   missing project_id"* — the id was nested under `data`.
3. **Status fields are per-stage and inconsistent:** graph/report tasks report
   `status: "completed"`; prepare completes as `status: "ready"`; a finished run
   reports `runner_status: "completed"` with `current_round`/`total_rounds` (no
   `progress`). `graph_id` arrives nested under the build task's `result`.

The fix was to **unwrap the envelope once in the transport layer** and model each
stage's terminal condition explicitly — turning a pile of `.get()` guesses into a
small, correct state machine.

## 3. Modeling it as a polled state machine

The real client (`atlas/prediction/mirofish.py`) drives the pipeline stage by stage,
each with its own completion predicate, under a single **wall-clock deadline** so a
stuck stage fails instead of hanging forever. Because the whole thing is
stdlib-`urllib` (no `requests`), it also hand-rolls a multipart encoder for the
seed-document upload.

Crucially, the tests exercise the **entire 6-stage flow against a mocked HTTP layer**
that returns the *real* enveloped shapes and drives the poll loop through multiple
iterations — so the orchestration is verified without a running backend.

## 4. The failure that became a feature

The first real end-to-end run got through four stages, then failed at `start` with a
cryptic HTTP 400: *"simulation not ready, status: failed."* The verbose trace showed
why — `entities_count: 0`. The seed was a single sentence, so MiroFish extracted no
entities, built an empty world, and had no agents to simulate.

That's not a bug to swallow — it's a usage constraint worth surfacing. The client now
inspects the prepare result and, on zero entities, raises an **actionable** error:

> MiroFish generated 0 agents from the seed material. The input is too thin to build
> a social world — provide a richer seed document (background, named
> people/teams/orgs, stakeholder context), not a one-line message.

## Takeaways

- **Interfaces before knowledge.** A `PredictionClient` + stub let the feature ship
  and stay tested while the real API was still a mystery.
- **Read the source, don't guess the contract.** Every real fix came from the Flask
  code, not trial and error against a slow, credit-burning backend.
- **Fail loudly and usefully.** The most valuable error in the system explains a data
  requirement in plain language instead of leaking a downstream 400.
