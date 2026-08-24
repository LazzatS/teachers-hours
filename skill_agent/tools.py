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

# Thresholds for the reteach decision. Deliberately explicit and tunable:
# this is the pedagogical judgment call at the heart of the product, so it
# lives in code a teacher can inspect, not inside a prompt.
MASTERED_AT = 0.85       # at or above: class has it, move on
CLASS_GAP_AT = 0.35      # at or below: reteach to the whole class


def diagnose(topic_id: str) -> dict:
    """Aggregates graded submissions per skill and decides what to reteach.

    Args:
        topic_id: The topic identifier.

    Returns:
        Per-skill pass rates with a verdict of mastered, individual_gap or
        class_gap, the students who missed each skill, and per-student counts
        of prerequisite gaps and procedural slips.
    """
    topic_ref = db.collection("topics").document(topic_id)
    skills = {s.id: s.to_dict()["name"] for s in topic_ref.collection("skills").stream()}

    tally = {sid: {"correct": 0, "total": 0, "missed_by": []} for sid in skills}
    prerequisite_gaps = {}
    procedural_slips = {}
    ungraded = 0

    for sub in topic_ref.collection("submissions").stream():
        d = sub.to_dict()
        sid = d.get("skill_id")
        if sid not in tally:
            continue
        if not d.get("graded"):
            ungraded += 1
            continue

        student = d["student_id"]
        error_type = d.get("error_type", "")

        # Pass rate is about the skill, so a procedural slip still counts as
        # having demonstrated it. Fall back to `correct` for older documents.
        demonstrated = d.get("skill_demonstrated", d.get("correct", False))

        tally[sid]["total"] += 1
        if demonstrated:
            tally[sid]["correct"] += 1
        else:
            tally[sid]["missed_by"].append(student)

        if error_type in ("prerequisite", "procedural"):
            bucket = prerequisite_gaps if error_type == "prerequisite" else procedural_slips
            bucket.setdefault(student, []).append({
                "skill": skills[sid],
                "misconception": d.get("misconception", ""),
            })

    results = []
    for sid, t in sorted(tally.items()):
        if t["total"] == 0:
            continue
        rate = t["correct"] / t["total"]
        if rate >= MASTERED_AT:
            verdict = "mastered"
        elif rate <= CLASS_GAP_AT:
            verdict = "class_gap"
        else:
            verdict = "individual_gap"
        results.append({
            "skill_id": sid,
            "skill": skills[sid],
            "pass_rate": round(rate, 2),
            "correct": t["correct"],
            "total": t["total"],
            "verdict": verdict,
            "missed_by": sorted(t["missed_by"]),
        })

    topic_ref.collection("verdicts").document("latest").set({
        "results": results,
        "ungraded": ungraded,
        "prerequisite_gaps": prerequisite_gaps,
        "procedural_slips": procedural_slips,
        "computed_at": firestore.SERVER_TIMESTAMP,
        "thresholds": {"mastered_at": MASTERED_AT, "class_gap_at": CLASS_GAP_AT},
    })

    return {
        "status": "ok",
        "results": results,
        "ungraded": ungraded,
        "prerequisite_gaps": prerequisite_gaps,
        "procedural_slips": procedural_slips,
    }
