import uuid
from google.cloud import firestore
from google.adk.agents import Agent

DB_NAME = "teachers-hours"
db = firestore.Client(database=DB_NAME)

def save_skills(topic: str, skills: list[str]) -> dict:
    """Saves a topic and its skill breakdown to Firestore.

    Args:
        topic: The school topic, e.g. "Chemistry: Atomic Structure".
        skills: Ordered list of skills a student must master.

    Returns:
        Status, the generated topic_id, and how many skills were saved.
    """
    topic_id = str(uuid.uuid4())[:8]
    topic_ref = db.collection("topics").document(topic_id)
    topic_ref.set({
        "title": topic,
        "status": "skills_drafted",
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    for i, name in enumerate(skills):
        topic_ref.collection("skills").document(f"s{i + 1}").set({
            "name": name,
            "order": i + 1,
            "approved": False,
        })
    return {"status": "ok", "topic_id": topic_id, "skill_count": len(skills)}


root_agent = Agent(
    name="skill_agent",
    model="gemini-3.5-flash",
    description="Breaks a school topic into teachable skills and saves them.",
    instruction=(
        "When the teacher gives you a school topic, break it into the distinct "
        "skills a student must master to understand it. Keep skills concrete "
        "and individually assessable. Then call save_skills with the topic and "
        "the ordered skill list. Tell the teacher the topic_id and the skills."
    ),
    tools=[save_skills],
)
