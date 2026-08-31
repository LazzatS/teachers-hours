# Teacher's Hours

**Get your hours back. Keep your judgment.**

A teacher types a topic. An agent breaks it into assessable skills, writes
leveled problems, grades what students submit, and then decides what actually
needs reteaching in class — and what one student can work on alone.

Built for the All Things Agentic Hackathon (**Taskmaster** track), Aug 21–31 2026.

- **Live:** https://teachers-hours-455997608773.europe-west1.run.app
- **Demo video:** [YOUTUBE](https://youtu.be/ktpbkSvf0vI)
- **Architecture:** [docs/architecture.png](docs/architecture.png)

---

## The problem

Preparing a lesson is not the hard part of teaching. The hard part is knowing
what landed. A teacher who assigns homework to thirty students gets thirty
pieces of paper back and no time to turn them into a decision about tomorrow's
lesson. So the decision gets made on instinct, or not at all.

## What it does

1. **Topic → skills.** The teacher types "Physics: Speed, Distance and Time".
   The agent breaks it into distinct, individually assessable skills.
2. **The teacher corrects it.** Reword a skill, delete one, add the one the
   agent missed. Corrections are recorded.
3. **Skills → leveled problems.** Three per skill — low, medium, hard. Open
   response only, because the grader needs to see the working.
4. **Assign to a class** with a deadline. The roster is snapshotted at
   assignment time.
5. **Students submit.** Each submission publishes an event. Nobody presses
   anything.
6. **Grading happens in the background.** A separate service consumes the
   events and grades each answer against the skill it was meant to test.
7. **The verdict.** Pass rates per skill, classified into: reteach to the whole
   class, individual gaps with named students, or mastered — move on.
8. **One note per student**, composed from their own results, held until the
   teacher releases it.

## The part that makes it more than a grader

A wrong answer is not one thing. The grader separates:

| | meaning | response |
|---|---|---|
| `target_skill` | hasn't grasped the skill under test | reteach the concept |
| `prerequisite` | failed on an earlier skill (rounding, fractions) | teach the earlier skill |
| `procedural` | right method, slipped arithmetic | accuracy practice, not reteaching |

A procedural slip counts as **having demonstrated the skill**, so it never
lowers a skill's pass rate. Reteaching a concept a student already holds is the
wrong response to a dropped decimal.

In a real run on multi-digit addition, two students failed the same skill and
got different diagnoses: one was told to slow down and check her arithmetic,
the other that he had rounded to the nearest ten instead of the hundred.

## Where the judgment lives

The classification is **computed in Python, not asked of a model**:

```python
MASTERED_AT  = 0.85   # at or above: the class has it
CLASS_GAP_AT = 0.35   # at or below: reteach to everyone
```

Gemini turns those numbers into something a teacher can read; it does not
decide them. During development the class-gap threshold was 0.50 and flagged
five of seven skills for whole-class reteaching — technically correct, useless
to a teacher. Moving it to 0.35 produced one clear reteach and named
individuals. That threshold *is* the pedagogical judgment, so it lives where a
teacher could inspect and tune it.

The same principle governs the approval gate: `list_approved_skills` filters on
`approved == True`, so the problem-generating agent structurally cannot see
unapproved skills. The constraint is in the data layer, not in a prompt that
might be skipped.

**The rule for human approval:** the teacher approves anything that reaches a
student — the problems, and the feedback. Everything internal — skills,
grading, aggregation — the agent does alone.

## Architecture

```
Teacher (ADK web UI)          Students (seeded for v1)
        │                              │
        ▼                              ▼
  Cloud Run: ADK agent            submissions
  coordinator                          │
   ├── skill_agent                     ▼
   ├── problem_agent               Pub/Sub topic
   └── diagnostic_agent                │
        │                              ▼
        │                     Cloud Run: grader (private)
        │                     Gemini grades each answer
        ▼                              │
     Firestore  ◄─────────────────────-┘
     topics · skills · problems · submissions · verdicts · notes
```

- **Gemini 3.5 Flash** via Vertex AI (`global` endpoint)
- **Agent Development Kit (ADK)**, Python — one coordinator, three sub-agents
- **Cloud Run** — two services: the conversational agent, and the grading worker
- **Firestore** — all state
- **Pub/Sub** — submission events, OIDC-authenticated push to a private service

The grader is deliberately a separate service. It is triggered by an event, not
by conversation, which is what makes the grading autonomous rather than
requested.

It is also idempotent: Pub/Sub delivers at least once, and on the first real run
it redelivered messages while grading was still in flight. Without the
`graded` check, half the class would have been graded twice.

## Running it

Requires a Google Cloud project with Vertex AI, Cloud Run, Firestore and
Pub/Sub enabled, and a Firestore database in Native mode.

```bash
git clone git@github.com:LazzatS/teachers-hours.git && cd teachers-hours
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `skill_agent/.env` (gitignored — you must write this yourself):

```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
```

`GOOGLE_CLOUD_LOCATION` must be `global` or a region that serves Gemini 3.5
Flash. `europe-west1` does not, which will produce a 404 on the model.

If your Firestore database is named rather than `(default)`, set `DB_NAME` in
`skill_agent/tools.py` and `grader/main.py` to match.

```bash
adk web                      # local, http://localhost:8000
```

Deploy both services:

```bash
PROJECT_ID=your-project ./deploy.sh          # the ADK agent
cd grader && gcloud run deploy grader --source . \
  --region=europe-west1 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=your-project && cd ..
```

Pub/Sub wiring (once):

```bash
gcloud pubsub topics create submissions
gcloud iam service-accounts create pubsub-invoker
gcloud run services add-iam-policy-binding grader --region=europe-west1 \
  --member=serviceAccount:pubsub-invoker@PROJECT.iam.gserviceaccount.com \
  --role=roles/run.invoker
gcloud projects add-iam-policy-binding PROJECT \
  --member=serviceAccount:service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com \
  --role=roles/iam.serviceAccountTokenCreator
gcloud pubsub subscriptions create submissions-push \
  --topic=submissions \
  --push-endpoint=https://YOUR-GRADER-URL/pubsub \
  --push-auth-service-account=pubsub-invoker@PROJECT.iam.gserviceaccount.com
```

Seed a class's submissions:

```bash
python seed_submissions.py <topic_id>
```

## Reproducible testing

With `adk web` running at http://localhost:8000:

1. Type a topic: `Maths: Linear Equations`
2. The agent proposes skills. Reply `approve` (or `add a skill solve
   one-step equations mentally` first, to see teacher corrections).
3. Problems generate for each approved skill.
4. Reply `create a class called 9B for Maths with ayan, dana, erlan and
   madina`, then `assign to 9B, due in 48 hours`.
5. Note the topic id from the conversation, then seed submissions:
   `python seed_submissions.py <topic_id>`
6. Wait ~30 seconds for the grading worker, then ask
   `how did my class do?`

Expected: one skill flagged for whole-class reteach, individual gaps with
named students, at least one procedural slip identified separately, and one
composed feedback note per student held for release.

## Scope and disclosure

**Student submissions are simulated.** The student-facing app is out of scope
for this build. `seed_submissions.py` asks Gemini for three kinds of answer per
problem — correct, a procedural slip, and a conceptual error — and records
which kind it intended. Everything downstream (grading, aggregation, the
verdict, the notes) runs on them exactly as it would on real submissions, and
the grader classifies them independently: it reproduced the seeded intent
without being told what it was.


## What's next

- **Student app.** A per-student page for submitting and reading feedback,
  replacing the seed script.
- **Deadline-triggered diagnosis.** Cloud Scheduler computing the verdict when
  the deadline passes, so the teacher is notified rather than having to ask.
- **Cross-subject prerequisite tracking.** If a student's `prerequisite`
  failures point at fractions in both chemistry and physics, that is a finding
  no single teacher can see alone.
- **Learning from corrections.** `edited_by_teacher` already records where the
  agent's skill breakdown fell short; that is training signal.
- **Minimum coverage before a class-wide verdict.** With four students, one
  failure moves a pass rate by 25%; thresholds should not fire on thin data.

Not planned: inferring personality or learning-style types from submission
data. The subjects are children, submissions cannot support that inference, and
a wrong label follows a child. The system reports evidence and leaves
interpretation to the teacher.

## Build log

[BUILDLOG.md](BUILDLOG.md) — what broke and what fixed it, day by day.
