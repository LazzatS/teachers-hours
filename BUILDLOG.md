### Aug 21
- Enabled 6 APIs; hit 429 RESOURCE_EXHAUSTED — Service Usage caps mutate
  requests at 120/min and a fresh project blows through it. Waited 2 min, re-ran.
- Console search for "Firestore" surfaced Filestore (managed NFS) — different
  product, wanted a VPC service connection policy. Backed out, found Firestore.

### Aug 22
- Vertex AI 404: gemini-3.5-flash isn't served from europe-west1.
  Set GOOGLE_CLOUD_LOCATION=global for the model; Firestore + Cloud Run stay
  in europe-west1. Model endpoint and infra region are independent settings.
- adk deploy needs the agent folder as a positional arg (./skill_agent);
  adk web auto-discovers it, deploy doesn't.
- Deploy failed 403: default compute SA couldn't read the source zip from GCS.
  New projects don't auto-grant Cloud Build roles. Fixed with
  roles/cloudbuild.builds.builder + roles/aiplatform.user.
- Deployed: https://teachers-hours-455997608773.europe-west1.run.app
- Deployed service 404'd on the model while local worked: .env is gitignored,
  so it never shipped. Cloud Run defaults GOOGLE_CLOUD_LOCATION to the deploy
  --region (europe-west1), which doesn't serve gemini-3.5-flash. Fixed by
  setting env vars on the service post-deploy; wrapped both steps in deploy.sh
  so they can't drift apart again.
- Named vs (default) Firestore databases, and that client libraries assume 
  (default) unless told otherwise.
- Split one agent into a coordinator with skill_agent + problem_agent
  sub-agents. Approval is enforced structurally: list_approved_skills filters
  on approved==True, so problem_agent literally cannot see unapproved skills.
- All-or-nothing approval didn't match how teachers review — added
  edit_skill / remove_skill / add_skill so corrections happen in conversation.
- Seeded 4 simulated students with a designed pass-rate pattern (one skill
  passes 4/4, another 1/4) so aggregation has a real verdict to produce.
  Pub/Sub events confirmed via `subscriptions pull`.

### Aug 23
- Grader deployed as a second Cloud Run service, triggered by Pub/Sub push
  rather than by conversation. Build failed twice first: main.py wasn't saved
  into grader/, and I deployed from the parent dir (--source . uploads the
  *current* folder).
- Secured with OIDC instead of --allow-unauthenticated: dedicated
  pubsub-invoker SA with run.invoker, Pub/Sub granted
  serviceAccountTokenCreator, subscription recreated with push auth.
- The idempotency guard earned itself on the first run — grading takes several
  seconds, ack deadlines lapsed, and Pub/Sub redelivered. "already graded,
  skipping" throughout the logs. Without it, half the class double-graded.
- Split failure handling: JSONDecodeError escalates to the teacher
  (needs_review), transient errors return 500 so Pub/Sub retries. Same-looking
  errors, opposite correct responses.
- One submission never arrived — publish-side loss, nothing in the grader logs.
  Republished by hand. At-least-once delivery only holds if the publish lands.
- Grader independently reproduced the seeded pattern (s1 4/4 → s4 1/4), so it's
  judging understanding, not matching strings.
- Aggregation + reteach verdict. Deliberate split: pass rates and
  classification are computed in Python; Gemini only turns the numbers into
  teacher-readable advice. The pedagogical judgment is auditable, not
  buried in a prompt.
- First threshold (class_gap at 0.50) flagged 5 of 7 skills for whole-class
  reteaching — technically correct, useless to a teacher. Dropped to 0.35 and
  the output became one class-wide gap plus named individuals. The threshold
  IS the product decision; that's the argument for keeping it in code where a
  teacher could tune it per class.
- Third sub-agent (diagnostic_agent) added to the coordinator.

### Aug 24
- grader returns skill_demonstrated / answer_correct / error_type /
  misconception. A procedural slip (right method, wrong arithmetic) no longer
  counts against a skill's pass rate — reteaching a concept the student
  already has is the wrong response to a dropped decimal.
- MCQ problems break the taxonomy — a student who picks "B" shows no working,
  so there's nothing to classify. Problem agent now generates open-response only.
- First aggregation of the new error types returned counts ({"madina": 2}),
  which tells a teacher nothing. Changed it to carry the skill name and the
  grader's misconception text. Aggregation should preserve evidence, not
  just tally it.
- Seed script now generates three answer kinds per problem and records
  seeded_intent, so the grader's classification can be checked against what
  was intended rather than assumed.

### Aug 25
- Classes are their own collection now. Topics store a roster *snapshot* taken
  at assignment time, not a live reference — if a student joins in October, a
  September assignment's coverage numbers must not change retroactively.
- Coverage-aware diagnosis: pass rates are computed over submitted work only.
  A missing submission is never counted as a wrong answer. Not submitting is a
  chasing-students problem; not understanding is a teaching problem, and
  conflating them would make the verdict lie.
- Killed IDs in the teacher's conversation. The agent was asking for topic_id
  and class_id — teachers aren't programmers. Added find_topic (search by
  title fragment), made assign_to_class resolve classes by name, and forbade
  the coordinator from ever asking for an internal id. The fix wasn't a UI; it
  was making the agent hold context it already had.
- Full error taxonomy fired end to end on a logarithms topic: class-wide gap,
  individual gaps, a repeat-student signal, a procedural slip, and prerequisite
  gaps naming the specific missing skills (fractional exponents, factoring
  quadratics). Two students failing the same skill got different diagnoses —
  one needs accuracy practice, the other needs an earlier skill retaught.
- Assigned a topic without a due date by accident and got a verdict anyway.
  Made diagnose() refuse when roster is empty rather than reporting on partial
  data. Same principle as list_approved_skills filtering on approved==True:
  constraints belong in code, not in prompt instructions that can be skipped.

### Aug 27
- The agent kept stopping to ask "anything else?" after approving skills, and
  re-asking for approval after every single edit. Both are chatbot reflexes,
  not agent behaviour — and the track is judged on completing work without
  hand-holding. Approval of the skills IS approval to generate problems, so
  the handoff now happens immediately; edits show the revised list and stop,
  with no re-prompt until the teacher approves.

### Aug 28
- Feedback needed its own composition step. The grader judges one answer at a
  time, so releasing raw per-submission feedback would send a student sixteen
  disconnected sentences. Added list_student_results (group by student),
  save_student_note (one composed note, 4-6 sentences), release_notes.
- The rule that makes the notes readable: one sentence per skill they got
  wrong, all the skills they got right compressed into one, and mistakes of
  the same kind grouped rather than repeated — three arithmetic slips are one
  point, not three.
- Worth naming: the aggregation that serves the teacher and the one that
  serves the student are different shapes. The teacher needs per-skill and
  class-wide; the student needs one paragraph about themselves. Same graded
  data, two compositions — which is why composition is its own step rather
  than concatenating feedback strings.
- Deleted release_feedback / edit_feedback / list_drafted_feedback: they
  operated on submissions, and two competing release paths would leave the
  teacher unsure which one actually reached the student. Editing is just
  re-calling save_student_note, which overwrites and keeps released=false.
