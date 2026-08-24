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
