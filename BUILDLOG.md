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
