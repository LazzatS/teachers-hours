import uuid
from google.cloud import firestore

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
    ref = db.collection("topics").document(topic_id)
    ref.set({"title": topic, "status": "skills_drafted",
             "created_at": firestore.SERVER_TIMESTAMP})
    for i, name in enumerate(skills):
        ref.collection("skills").document(f"s{i + 1}").set(
            {"name": name, "order": i + 1, "approved": False})
    return {"status": "ok", "topic_id": topic_id, "skill_count": len(skills)}


def edit_skill(topic_id: str, skill_id: str, new_name: str) -> dict:
    """Rewrites the name of one skill.

    Args:
        topic_id: The topic identifier.
        skill_id: The skill to change, e.g. "s2".
        new_name: The teacher's corrected wording for the skill.

    Returns:
        Status and the updated skill.
    """
    (db.collection("topics").document(topic_id)
       .collection("skills").document(skill_id)
       .update({"name": new_name, "edited_by_teacher": True}))
    return {"status": "ok", "skill_id": skill_id, "name": new_name}


def remove_skill(topic_id: str, skill_id: str) -> dict:
    """Deletes a skill the teacher judged unnecessary.

    Args:
        topic_id: The topic identifier.
        skill_id: The skill to remove, e.g. "s3".

    Returns:
        Status and the removed skill id.
    """
    (db.collection("topics").document(topic_id)
       .collection("skills").document(skill_id).delete())
    return {"status": "ok", "removed": skill_id}


def add_skill(topic_id: str, name: str) -> dict:
    """Adds a skill the teacher wants included.

    Args:
        topic_id: The topic identifier.
        name: The skill to add.

    Returns:
        Status and the new skill id.
    """
    ref = db.collection("topics").document(topic_id).collection("skills")
    existing = list(ref.stream())
    skill_id = f"s{len(existing) + 1}"
    ref.document(skill_id).set({
        "name": name, "order": len(existing) + 1,
        "approved": False, "added_by_teacher": True,
    })
    return {"status": "ok", "skill_id": skill_id, "name": name}
    

def approve_skills(topic_id: str) -> dict:
    """Marks every skill in a topic as approved by the teacher.

    Args:
        topic_id: The topic identifier returned by save_skills.

    Returns:
        Status and the number of skills approved.
    """
    ref = db.collection("topics").document(topic_id)
    skills = list(ref.collection("skills").stream())
    for s in skills:
        s.reference.update({"approved": True})
    ref.update({"status": "skills_approved"})
    return {"status": "ok", "approved_count": len(skills)}


def list_approved_skills(topic_id: str) -> dict:
    """Returns the approved skills for a topic, ready for problem generation.

    Args:
        topic_id: The topic identifier.

    Returns:
        Status and a list of approved skills with their ids and names.
    """
    ref = db.collection("topics").document(topic_id)
    skills = [{"skill_id": s.id, "name": s.to_dict()["name"]}
              for s in ref.collection("skills").where("approved", "==", True).stream()]
    return {"status": "ok", "skills": skills}


def save_problems(topic_id: str, skill_id: str, low: str, medium: str, hard: str) -> dict:
    """Saves three difficulty-tiered problems for one skill.

    Args:
        topic_id: The topic identifier.
        skill_id: The skill identifier, e.g. "s1".
        low: An easy problem testing this skill.
        medium: A moderate problem testing this skill.
        hard: A challenging problem testing this skill.

    Returns:
        Status and the skill the problems were saved under.
    """
    ref = (db.collection("topics").document(topic_id)
             .collection("skills").document(skill_id)
             .collection("problems"))
    for level, text in (("low", low), ("medium", medium), ("hard", hard)):
        ref.document(level).set({"level": level, "text": text})
    return {"status": "ok", "skill_id": skill_id}
