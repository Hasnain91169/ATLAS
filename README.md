# ATLAS

**A personal "operating company" assistant.** ATLAS models your work like a small
organization: department *heads* produce reports, an orchestrator (Atlas) synthesizes
them, and the system proposes concrete actions you can review and approve. It includes a
daily brief, risk alerts, hourly planning, email triage, board-meeting reports (with
optional text-to-speech), Google Tasks sync, and a local mobile server.

> Status: early (v0.1.0). Interfaces may change.

## Requirements

- Python **3.11+**
- Runtime dependencies: [`pydantic`](https://docs.pydantic.dev/) and `PyYAML` (installed
  automatically). External integrations (OpenAI, ElevenLabs, Google Tasks) are optional
  and activated via environment variables.

## Installation

```bash
git clone <your-repo-url> atlas
cd atlas
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `atlas` console command.

## Configuration

Most commands take a YAML config via `--config`. Data is persisted to a local SQLite
database whose default location is:

- **Windows:** `%LOCALAPPDATA%\atlas\atlas.db`
- **macOS/Linux:** `~/.atlas/atlas.db`

Override the path on any command with `--db /path/to/atlas.db`.

### Environment variables

External services are opt-in. A command only requires a key when you invoke a feature
that uses it.

| Variable | Used by | Required for |
| --- | --- | --- |
| `OPENAI_API_KEY` | LLM features | Any LLM-backed reasoning |
| `OPENAI_MODEL` | LLM features | Optional (default `gpt-5-mini`) |
| `OPENAI_BASE_URL` | LLM features | Optional (custom/proxy endpoint) |
| `ELEVENLABS_API_KEY` | Board-meeting `speak` | Generating audio |
| `ELEVENLABS_MODEL` | Board-meeting `speak` | Optional (default `eleven_multilingual_v2`) |
| `GOOGLE_TASKS_CLIENT_ID` | `tasks sync` | Google Tasks sync |
| `GOOGLE_TASKS_CLIENT_SECRET` | `tasks sync` | Google Tasks sync |
| `GOOGLE_TASKS_REFRESH_TOKEN` | `tasks sync` | Google Tasks sync |
| `ATLAS_MOBILE_TOKEN` | `atlas serve` | Starting the mobile server |

Never commit these values — set them in your shell or a local, git-ignored `.env`.

## Usage

Run `atlas --help` to see all commands. Highlights:

```bash
# Generate deterministic demo artifacts and populate the database
atlas demo --config config.yaml

# Daily brief
atlas daily-brief --config config.yaml

# Hourly plan for today
atlas hourly-plan --config config.yaml

# Triage a set of messages (.yaml / .yml / .jsonl)
atlas email-triage --input examples/messages.yaml

# Board meeting: print report, then synthesize audio per head
atlas board-meeting report
atlas board-meeting speak            # requires ELEVENLABS_API_KEY

# Run hierarchical org reports (heads -> Atlas synthesis)
atlas org run

# Propose / review / approve actions
atlas actions propose
atlas actions list
atlas actions approve <action_id>

# Google Tasks (read-only sync into local DB)
atlas tasks sync --config config.yaml
atlas tasks list

# Risk alerts
atlas alerts --severity HIGH

# Environment / connectivity check
atlas doctor

# Local mobile server (LAN only, token required)
atlas serve            # requires ATLAS_MOBILE_TOKEN
```

See `examples/messages.yaml` for a sample input file.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The `tests/` directory contains the full suite (unit + CLI coverage).

## Project layout

```
atlas/
  actions/       Action proposal, models, and execution
  agents/        Agent drafting and context
  board_meeting/ Report building, splitting, manifests
  brief/         Daily brief generation, scoring, tagging
  calendar/      Calendar interfaces (stub)
  llm/           LLM client (OpenAI)
  mobile/        Local mobile server
  models/        Pydantic data models
  org/           Hierarchical orchestrator + protocol
  risk/          Risk rules and alerts
  storage/       SQLite persistence + schema
  tasks/         Task providers (Google, stub)
  tts/           Text-to-speech (ElevenLabs), chunking, voices
  workflows/     End-to-end workflows
tests/           Test suite
examples/        Sample inputs
scripts/         Helper scripts
static/          Mobile web client
```

## License

Released under the [MIT License](LICENSE).
