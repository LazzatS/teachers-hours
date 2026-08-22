# Teacher's Hours

**Get your hours back. Keep your judgment.**

An agent that turns a topic into skills, generates leveled problems, grades
student submissions, and decides what needs reteaching in class versus what a
student can self-study.

Built for the All Things Agentic Hackathon — Taskmaster track.

## Stack

- Gemini 3.5 Flash via Vertex AI (global endpoint)
- Agent Development Kit (ADK), Python
- Cloud Run · Firestore · Pub/Sub — all `europe-west1`

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
adk web
```

Requires a `.env` in `skill_agent/` with `GOOGLE_GENAI_USE_VERTEXAI=TRUE`,
`GOOGLE_CLOUD_PROJECT`, and `GOOGLE_CLOUD_LOCATION=global`.

## Deploy

```bash
PROJECT_ID=your-project ./deploy.sh
```

## Status

In development — see [BUILDLOG.md](BUILDLOG.md).
