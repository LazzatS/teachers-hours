"""Grading worker — triggered by Pub/Sub, not by the teacher.

Pub/Sub pushes one message per submission to /pubsub. This service grades that
submission with Gemini and writes the result back to Firestore. Nobody clicks
anything: the teacher can be teaching while this runs.
"""

import json
import os

from fastapi import FastAPI, Request, Response
from google import genai
from google.cloud import firestore

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "teachers-hours-506217")
DB_NAME = "teachers-hours"

app = FastAPI()
db = firestore.Client(database=DB_NAME)
client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")


def grade(problem: str, skill: str, answer: str) -> dict:
    """Grades one answer against the skill it was meant to test."""
    prompt = (
        f"Skill being tested: {skill}\n"
        f"Problem: {problem}\n"
        f"Student answer: {answer}\n\n"
        "Decide whether the student has demonstrated this skill. Judge the "
        "understanding, not the wording or spelling. If it is wrong, name the "
        "specific misconception in one sentence a student would understand.\n\n"
        "Return only JSON, no markdown fences:\n"
        '{"correct": true or false, "feedback": "one or two sentences"}'
    )
    resp = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
    text = resp.text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


@app.post("/pubsub")
async def handle(request: Request) -> Response:
    envelope = await request.json()
    attrs = envelope.get("message", {}).get("attributes", {}) or {}
    topic_id = attrs.get("topic_id")
    submission_id = attrs.get("submission_id")

    if not topic_id or not submission_id:
        # Malformed — ack it, because retrying will not help.
        print(f"bad message, dropping: {attrs}")
        return Response(status_code=204)

    topic_ref = db.collection("topics").document(topic_id)
    sub_ref = topic_ref.collection("submissions").document(submission_id)
    sub = sub_ref.get()

    if not sub.exists:
        print(f"no submission {submission_id}, dropping")
        return Response(status_code=204)

    data = sub.to_dict()

    # Pub/Sub guarantees at-least-once delivery, so the same message can
    # arrive twice. Grading twice would cost money and could flip a result.
    if data.get("graded"):
        print(f"{submission_id} already graded, skipping")
        return Response(status_code=204)

    skill_ref = topic_ref.collection("skills").document(data["skill_id"])
    skill = skill_ref.get().to_dict()
    problem = skill_ref.collection("problems").document(data["level"]).get().to_dict()

    try:
        result = grade(problem["text"], skill["name"], data["answer"])
    except json.JSONDecodeError as e:
        # The model's output wasn't parseable. Retrying won't help, and this
        # answer shouldn't vanish — escalate it to the teacher instead.
        print(f"unparseable grading response for {submission_id}: {e}")
        sub_ref.update({
            "graded": True,
            "correct": False,
            "needs_review": True,
            "feedback": "This answer needs the teacher's eye.",
            "feedback_released": False,
        })
        return Response(status_code=204)
    except Exception as e:
        # Transient failure (network, quota) — 500 tells Pub/Sub to redeliver.
        print(f"grading failed for {submission_id}: {e}")
        return Response(status_code=500)

    sub_ref.update({
        "graded": True,
        "correct": bool(result["correct"]),
        "feedback": result["feedback"],
        "feedback_released": False,
        "graded_at": firestore.SERVER_TIMESTAMP,
    })
    print(f"graded {submission_id}: correct={result['correct']}")
    return Response(status_code=204)


@app.get("/")
def health() -> dict:
    return {"status": "ok"}
