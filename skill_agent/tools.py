import uuid
from google.cloud import firestore
from datetime import datetime, timedelta, timezone
import re

DB_NAME = "teachers-hours"
db = firestore.Client(database=DB_NAME)

# STUDENT skills

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
    
    topic_data = topic_ref.get().to_dict() or {}
    roster = topic_data.get("roster", [])
    approved_skills = [sid for sid in skills]
    expected = len(roster) * len(approved_skills)
    submitted_pairs = set()

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
        submitted_pairs.add((student, sid))
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

    missing_by_student = {}
    for student in roster:
        missing = [sid for sid in approved_skills if (student, sid) not in submitted_pairs]
        if missing:
            missing_by_student[student] = missing

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
        "coverage": {"expected": expected, "submitted": len(submitted_pairs),
             "missing_by_student": missing_by_student},
    })

    return {
        "status": "ok",
        "results": results,
        "ungraded": ungraded,
        "prerequisite_gaps": prerequisite_gaps,
        "procedural_slips": procedural_slips,
        "coverage": {"expected": expected, "submitted": len(submitted_pairs),
             "missing_by_student": missing_by_student},
    }
    

# CLASS information

def create_class(name: str, subject: str, students: list[str]) -> dict:
    """Creates a class the teacher can assign topics to.

    Args:
        name: What the teacher calls the class, e.g. "9B".
        subject: The subject taught, e.g. "Physics".
        students: The student identifiers in the class.

    Returns:
        Status, the class_id, and how many students were added.
    """
    class_id = re.sub(r"[^a-z0-9]+", "-", f"{name}-{subject}".lower()).strip("-")
    db.collection("classes").document(class_id).set({
        "name": name,
        "subject": subject,
        "students": students,
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    return {"status": "ok", "class_id": class_id, "size": len(students)}


def list_classes() -> dict:
    """Lists the classes the teacher has created.

    Returns:
        Status and each class with its id, name, subject and size.
    """
    classes = [{
        "class_id": c.id,
        "name": c.to_dict().get("name", ""),
        "subject": c.to_dict().get("subject", ""),
        "size": len(c.to_dict().get("students", [])),
    } for c in db.collection("classes").stream()]
    return {"status": "ok", "classes": classes}


def assign_to_class(topic_id: str, class_name: str, due_in_hours: int) -> dict:
    """Assigns a topic's approved problems to a class with a deadline.

    Args:
        topic_id: The topic identifier.
        class_name: What the teacher calls the class, e.g. "9B".
        due_in_hours: Hours from now until the work is due.

    Returns:
        Status, the roster size, and when the work is due.
    """
    matches = [c for c in db.collection("classes").stream()
               if c.to_dict().get("name", "").lower() == class_name.lower()]
               
    if not matches:
        names = [c.to_dict().get("name") for c in db.collection("classes").stream()]
        return {"status": "error", "message": f"No class '{class_name}'. Have: {names}"}
    class_doc = matches[0]

    students = class_doc.to_dict().get("students", [])
    due_at = datetime.now(timezone.utc) + timedelta(hours=due_in_hours)

    db.collection("topics").document(topic_id).update({
        "class_name": class_name,
        # Snapshot, not a live reference: if a student joins the class next
        # month, this assignment's coverage numbers must not change.
        "roster": students,
        "due_at": due_at,
        "assigned_at": firestore.SERVER_TIMESTAMP,
        "status": "assigned",
    })
    return {"status": "ok", "roster_size": len(students),
            "due_at": due_at.isoformat()}
            

def find_topic(title_fragment: str) -> dict:
    """Finds recent topics whose title matches what the teacher describes.

    Args:
        title_fragment: Any part of the topic title, e.g. "speed" or "photosynthesis".

    Returns:
        Status and matching topics with their ids, titles, status and due dates.
    """
    hits = []
    for t in db.collection("topics").order_by(
            "created_at", direction=firestore.Query.DESCENDING).limit(30).stream():
        d = t.to_dict()
        if title_fragment.lower() in d.get("title", "").lower():
            hits.append({"topic_id": t.id, "title": d.get("title"),
                         "status": d.get("status"), "class_id": d.get("class_id")})
    return {"status": "ok", "topics": hits[:5]}

def list_student_results(topic_id: str) -> dict:
    """Groups each student's graded results, ready for composing one note each.

    Args:
        topic_id: The topic identifier.

    Returns:
        Status and, per student, every skill with whether they demonstrated it,
        the error type, and the misconception.
    """
    topic_ref = db.collection("topics").document(topic_id)
    skills = {s.id: s.to_dict()["name"] for s in topic_ref.collection("skills").stream()}
    by_student = {}
    for sub in topic_ref.collection("submissions").stream():
        d = sub.to_dict()
        if not d.get("graded"):
            continue
        by_student.setdefault(d["student_id"], []).append({
            "skill": skills.get(d.get("skill_id"), ""),
            "demonstrated": d.get("skill_demonstrated", d.get("correct")),
            "error_type": d.get("error_type", ""),
            "misconception": d.get("misconception", ""),
        })
    return {"status": "ok", "students": by_student}


def save_student_note(topic_id: str, student_id: str, note: str) -> dict:
    """Saves one composed feedback note for a student, held until released.

    Args:
        topic_id: The topic identifier.
        student_id: Who the note is for.
        note: The composed feedback, 4-6 sentences.

    Returns:
        Status and the student the note was saved for.
    """
    (db.collection("topics").document(topic_id)
       .collection("notes").document(student_id)
       .set({"student_id": student_id, "note": note,
             "released": False, "drafted_at": firestore.SERVER_TIMESTAMP}))
    return {"status": "ok", "student_id": student_id}


def release_notes(topic_id: str, student_id: str = "") -> dict:
    """Releases composed notes to students, or to one student.

    Args:
        topic_id: The topic identifier.
        student_id: One student, or empty for everyone.

    Returns:
        Status and how many notes were released.
    """
    notes = db.collection("topics").document(topic_id).collection("notes")
    released = 0
    for n in notes.stream():
        if n.to_dict().get("released"):
            continue
        if student_id and n.id != student_id:
            continue
        n.reference.update({"released": True, "released_at": firestore.SERVER_TIMESTAMP})
        released += 1
    return {"status": "ok", "released": released}
