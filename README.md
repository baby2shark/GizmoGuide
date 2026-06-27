# GizmoGuide

GizmoGuide is a lightweight electronic product recommendation agent. The first version focuses on phone comparison: given candidate products and a user's budget, scenarios, preferences, and risks, it returns a personalized recommendation with reasons, risks, and reversal conditions.

## Current Scope

Implemented P0 and P1 basics:

- FastAPI project skeleton.
- Pydantic schemas for user profiles, products, and recommendations.
- Mock phone product data.
- Product matching.
- Rule-based user profile extraction.
- Clarification questions.
- Agent-first recommendation flow.\n- DeepSeek/OpenAI-compatible LLM client.\n- Product and scoring tools used by the Agent.\n- Dynamic scoring and constraints as guardrail tools.\n- Local fallback recommendation explanation.
- A zero-build frontend UI under `frontend/`.
- Unit tests for core P1 flow.

## Project Layout

```text
GizmoGuide/
  app/              # FastAPI backend and recommendation logic
  frontend/         # Vanilla HTML/CSS/JS frontend served at /ui/
  tests/            # P0/P1 tests
  requirements.txt
  pyproject.toml
```

## Install

```bash
pip install -r requirements.txt
```

In this Codex workspace, dependencies were installed into `.deps/`. To run with that local folder:

```powershell
$env:PYTHONPATH = '.deps;.'
```

## Run API and UI

```bash
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/ui/
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Example API Request

```json
{
  "user_message": "预算5000，主要拍照和日常用，想用三年，也在意维修",
  "candidate_products": ["iPhone 15", "vivo X100"]
}
```

POST it to `/recommend`.

## DeepSeek Configuration

Create `.env` from `.env.example` and set:

```text
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

When the key is present, `/recommend` uses the LLM Agent for the final decision. If the LLM call fails, the app falls back to the local scoring/template path.

## Notes

Do not edit the `pydantic-ai` source checkout for this project. This app owns its own code under `GizmoGuide/` and only depends on Pydantic/FastAPI packages.