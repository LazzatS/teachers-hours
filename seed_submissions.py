"""Seeds simulated student submissions for a topic.

Not part of the agent pipeline — this stands in for the student-facing app,
which is out of scope for v1. Run it once per topic to create demo data.

Usage:
    python seed_submissions.py <topic_id>
"""

import json
import os
import sys

from google import genai
from google.cloud import firestore, pubsub_v1

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "teachers-hours-506217")
DB_NAME = "teachers-hours"
PUBSUB_TOPIC = "submissions"
STUDENTS = ["ayan", "dana", "erlan", "madina"]

# Designed outcomes by skill position. Values: "correct", "procedural",
# "conceptual". Deliberately shaped so the diagnosis has something to say:
# s2 is a class-wide gap; madina slips procedurally rather than conceptually;
# erlan's failures are conceptual and repeated.
OUTCOME_BY_SKILL_POSITION = {
    1: {"ayan": "correct",    "dana": "correct",     "erlan": "correct",    "madina": "correct"},
    2: {"ayan": "conceptual", "dana": "conceptual",  "erlan": "conceptual", "madina": "procedural"},
    3: {"ayan": "correct",    "dana": "conceptual",  "erlan": "conceptual", "madina": "procedural"},
    4: {"ayan": "correct",    "dana": "correct",     "erlan": "conceptual", "madina": "correct"},
}
DEFAULT_OUTCOME = {"ayan": "correct", "dana": "correct",
                   "erlan": "conceptual", "madina": "procedural"}

db = firestore.Client(database=DB_NAME)
client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)


def answer_set(problem_text: str) -> dict:
    """Asks Gemini for a correct answer and two distinct kinds of wrong answer."""
    prompt = (
        "For this school problem, write three short student answers, each "
        "showing their working.\n"
        f"Problem: {problem_text}\n\n"
        "Return only JSON, no markdown fences:\n"
        '{"correct": "...", "procedural": "...", "conceptual": "..."}\n\n'
        '"procedural": the right method and setup, but one arithmetic or '
        "unit-conversion slip, giving a wrong final answer.\n"
        '"conceptual": a genuine misunderstanding of the skill itself — wrong '
        "formula or wrong relationship, not a slip.\n"
        "If the problem is definitional rather than calculated, make "
        '"procedural" an answer that is right in substance but omits or '
        "misstates the units."
    )
    resp = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
    text = (resp.text or "").replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def seed(topic_id: str) -> None:
    topic_ref = db.collection("topics").document(topic_id)
    if not topic_ref.get().exists:
        sys.exit(f"No topic {topic_id}")

    skills = sorted(
        topic_ref.collection("skills").stream(),
        key=lambda s: s.to_dict().get("order", 0),
    )
    written = 0
    futures = []

    for skill in skills:
        data = skill.to_dict()
        position = data.get("order", 0)
        problem = (
            skill.reference.collection("problems").document("medium").get()
        )
        if not problem.exists:
            print(f"  skip {skill.id} — no medium problem")
            continue

        answers = answer_set(problem.to_dict()["text"])
        if not all(k in answers for k in ("correct", "procedural", "conceptual")):
            print(f"  skip {skill.id} — model returned {list(answers)}")
            continue
        outcomes = OUTCOME_BY_SKILL_POSITION.get(position, DEFAULT_OUTCOME)

        for student in STUDENTS:
            kind = outcomes.get(student, "correct")
            sub_ref = topic_ref.collection("submissions").document(f"{student}_{skill.id}")
            sub_ref.set({
                "student_id": student,
                "skill_id": skill.id,
                "level": "medium",
                "answer": answers[kind],
                "seeded_intent": kind,     # for comparing against the grader
                "graded": False,
            })
            futures.append(publisher.publish(
                topic_path,
                b"",
                topic_id=topic_id,
                submission_id=sub_ref.id,
            ))
            written += 1

        counts = {}
        for k in outcomes.values():
            counts[k] = counts.get(k, 0) + 1
        summary = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
        print(f"  {skill.id} ({data['name'][:40]}) — {summary}")

    for f in futures:
        f.result()
    print(f"\nSeeded {written} submissions and published {written} events.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python seed_submissions.py <topic_id>")
    seed(sys.argv[1])
