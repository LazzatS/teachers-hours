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
