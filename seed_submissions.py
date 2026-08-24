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

# Designed outcome pattern, by skill position (1-indexed).
# Earlier skills mostly land; the last skill is a class-wide gap.
# This is what makes the aggregation produce an interesting verdict.
CORRECT_BY_SKILL_POSITION = {
    1: ["ayan", "dana", "erlan", "madina"],   # everyone gets it
    2: ["ayan", "dana", "erlan"],             # one student struggling
    3: ["ayan", "madina"],                    # borderline
    4: ["dana"],                              # class-wide gap
}
DEFAULT_CORRECT = ["ayan", "dana"]

db = firestore.Client(database=DB_NAME)
client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)


def answer_pair(problem_text: str) -> dict:
    """Asks Gemini for one correct answer and one realistically wrong answer."""
    prompt = (
        "For this school problem, write two short student answers.\n"
        f"Problem: {problem_text}\n\n"
        "Return only JSON, no markdown fences:\n"
        '{"correct": "...", "wrong": "..."}\n'
        "The wrong answer must reflect a plausible student mistake with the "
        "working shown. For calculation problems, vary the kind of mistake: "
        "sometimes the wrong formula (a conceptual error), sometimes the right "
        "method with a slipped unit conversion or arithmetic error."
    )
    resp = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
    text = resp.text.replace("```json", "").replace("```", "").strip()
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

    for skill in skills:
        data = skill.to_dict()
        position = data.get("order", 0)
        problem = (
            skill.reference.collection("problems").document("medium").get()
        )
        if not problem.exists:
            print(f"  skip {skill.id} — no medium problem")
            continue

        answers = answer_pair(problem.to_dict()["text"])
        correct_students = CORRECT_BY_SKILL_POSITION.get(position, DEFAULT_CORRECT)

        for student in STUDENTS:
            is_correct = student in correct_students
            sub_ref = topic_ref.collection("submissions").document(
                f"{student}_{skill.id}"
            )
            sub_ref.set({
                "student_id": student,
                "skill_id": skill.id,
                "level": "medium",
                "answer": answers["correct"] if is_correct else answers["wrong"],
                "graded": False,
            })
            publisher.publish(
                topic_path,
                b"",
                topic_id=topic_id,
                submission_id=sub_ref.id,
            )
            written += 1

        print(f"  {skill.id} ({data['name'][:40]}) — {len(correct_students)}/4 correct")

    print(f"\nSeeded {written} submissions and published {written} events.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python seed_submissions.py <topic_id>")
    seed(sys.argv[1])
