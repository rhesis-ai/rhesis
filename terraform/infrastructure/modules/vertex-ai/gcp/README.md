# vertex-ai/gcp

Per-environment Vertex AI identity: enables `aiplatform.googleapis.com`, creates
`rhesis-vertex-<env>`, and grants it `roles/aiplatform.user` in its own project.

## Why

Every environment used to authenticate as `gemini-vertex-sa@playground-437609` from a single
shared JSON key, and `vertexAiProject` was pinned to `playground-437609` in all three chart
value files. So dev, stg and prd all ran their Gemini traffic inside the retired Cloud Run
project. On 2026-09-02 disabling `aiplatform.googleapis.com` there took Vertex down in all
three environments at once for about 14 minutes.

## Cutover runbook

Terraform creates the identity but deliberately does not create the key, because
`google_service_account_key` writes the private key into Terraform state in plaintext.

Run one environment at a time, in the order dev, stg, prd, and verify before moving on.

### 1. Apply the Terraform

Merge the change and let `.github/workflows/terraform-infrastructure.yml` apply it. This
enables the API and creates the service account. It changes no traffic on its own.

dev and stg plan clean at `4 to add, 0 to change`. **prd needed drift reconciliation first**:
its ARC GitHub App secrets and the license mint secret were created by hand, so Terraform
planned to create them and would have aborted on `ALREADY_EXISTS` after changing live VPN
peering config. Those are adopted by `import` blocks in `envs/prd/main.tf`. If a future
environment plans more than the Vertex resources plus `local_file.cluster_env_<env>`, stop
and reconcile before applying rather than pushing through.

### 2a. Confirm the cluster actually derives the project from the key

**Stop here unless this prints an empty value.** This is the single check that would have
prevented the 2026-09-03 prd incident, and it costs one command:

```bash
CTX=connectgateway_rhesis-dev-494712_global_dev
kubectl --context="$CTX" -n rhesis get configmap rhesis-config \
  -o jsonpath='{.data.VERTEX_AI_PROJECT}'; echo "  <- must be empty"
```

Empty means the SDK takes the project from the credential (step 4), so the key is the single
source of truth and the two halves cannot drift apart. A **non-empty** value means the cluster is
still running an older render of `values-<env>.yaml` that pins `vertexAiProject`. Rotating the key
then puts the new service account against the old project and every Vertex call returns:

```
Permission 'aiplatform.endpoints.predict' denied on resource
'projects/<old-project>/locations/eu/publishers/google/models/...'
```

That is what happened to prd: its ArgoCD apps are pinned to a **commit**, not a branch, so the
merged chart change never reached the cluster while dev and stg picked it up. Merging is not
deploying. If the value is non-empty, confirm the app is on a revision that includes the change:

```bash
kubectl --context="$CTX" -n argocd get application rhesis \
  -o jsonpath='{.spec.source.targetRevision}{"  "}{.status.sync.status}{"\n"}'
```

### 2b. Check the models exist in the new project

Model availability is per project and per location, so confirm before cutting over. Note
`VERTEX_AI_LOCATION` is `eu` (a multi-region), not `europe-west4`, while
`VERTEX_AI_EMBEDDING_LOCATION` is `europe-west4`.

```bash
PROJECT=rhesis-dev-494712
TOKEN=$(gcloud auth print-access-token)
# Braces matter: in zsh, "$m:generateContent" parses as a history modifier and mangles the URL.
for m in gemini-3.1-flash-lite; do
  curl -s -o /dev/null -w "${m} %{http_code}\n" -X POST \
    -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
    "https://aiplatform.googleapis.com/v1/projects/${PROJECT}/locations/eu/publishers/google/models/${m}:generateContent" \
    -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}],"generationConfig":{"maxOutputTokens":5}}'
done
```

`gemini-2.0-flash` is retired and returns 404. It is still the SDK default in
`sdk/src/rhesis/sdk/models/defaults.py`, so anything relying on the default rather than the
`DEFAULT_*_MODEL` config will fail. Track that separately.

### 3. Mint the key and write it to Secret Manager

Use `--mint-vertex-key` on the existing secrets sync script; do not do this by hand:

```bash
S=infrastructure/config/gsm-secrets-sync.sh
bash "$S" --project rhesis-dev-494712 --json-env dev --mint-vertex-key --dry-run
bash "$S" --project rhesis-dev-494712 --json-env dev --mint-vertex-key
```

That script already owned publishing to Secret Manager, including the `printf '%s'` upsert
that avoids a trailing newline and the `secretmanager.secretAccessor` binding for ESO. The
flag changes only where the value comes from: instead of reading
`GOOGLE_APPLICATION_CREDENTIALS` out of `gsm-secrets.json`, it mints a fresh key for
`rhesis-vertex-<env>@<project>`. It then reads the published version back and decodes it
with the exact call the SDK makes, asserting `client_email` and `project_id`.

In this mode the script needs neither `gsm-secrets.json` nor `jq`, so rotating a credential
does not require a plaintext file of every other secret to be on disk.

Two failure modes are why this is a script rather than copy-paste steps, because both break
auth on every pod and neither is visible at the point of the mistake:

- The value must be **single-line base64 with no trailing newline**. The SDK calls
  `base64.b64decode(..., validate=True)`, which rejects a newline outright. GNU `base64`
  line-wraps at 76 characters (BSD/macOS does not), and a shell redirect adds a newline, so
  the script uses `tr -d '\n'` and `printf '%s'`.
- The key must belong to the environment's own project, since the project is derived from
  the key (see step 4). A key from the wrong project now succeeds silently against that
  project instead of failing with a 403.

The key never enters Terraform state, deliberately. `google_service_account_key` stores
`private_key` in state in plaintext, and all four CI service accounts hold
`storage.objectAdmin` on the entire state bucket with no per-prefix isolation, so a key in
one environment's state would be readable by the others. That also matches the existing
practice for the prd Cloudflare token, which is fetched in the CI action so it never reaches
state.

Preflight fails before minting anything if the service account does not exist, the secret
does not exist, or `eso-<env>@` lacks `secretmanager.secretAccessor` on it. The key file is
written with `umask 077` and shredded on exit, including on interrupt.

### 4. Nothing to change in the chart

The key is the only thing that moves. `vertexAiProject` is intentionally unset in every
values file, so the SDK derives the project from the key's own `project_id`
(`sdk/src/rhesis/sdk/models/providers/vertex_ai.py:219` only overrides it when the env var
is truthy). Identity and target project are therefore a single artifact and cannot drift
apart.

This is deliberate. When the project was pinned separately it travelled by a different
route from the key (ConfigMap and GitOps versus Secret Manager and ESO), which made the
cutover a two-place change where either half alone guarantees a 403: a new key has no role
in the old project, and the old key has none in the new one.

The ExternalSecret needs no edit either. The secret name is unchanged; only a new version
is added, and `eso-<env>@` already holds `roles/secretmanager.secretAccessor` on it.

The one thing this gives up: a wrong-project key used to fail loudly with a 403, and now it
would silently succeed against the wrong project. Catch that with the round-trip check in
step 3 and the per-project billing breakdown, not with a pinned value.

### 5. Refresh and restart

ESO has `refreshInterval: 1h`, and the secret reaches pods via `secretRef envFrom`, so env
vars are fixed at pod start. Both a resync and a restart are needed:

Resync first, and **confirm the Kubernetes Secret actually changed before restarting** —
restarting early just brings pods up on the old credential and teaches you nothing:

```bash
CTX=connectgateway_rhesis-dev-494712_global_dev
kubectl --context="${CTX}" -n rhesis annotate externalsecret rhesis-app-secrets \
  force-sync="$(date +%s)" --overwrite

kubectl --context="${CTX}" -n rhesis get secret rhesis-app-secrets \
  -o jsonpath='{.data.GOOGLE_APPLICATION_CREDENTIALS}' | base64 -d \
  | python3 -c "import sys,base64,json; d=json.loads(base64.b64decode(sys.stdin.read().strip(),validate=True)); print(d['client_email'],'->',d['project_id'])"

kubectl --context="${CTX}" -n rhesis rollout restart \
  deploy/backend deploy/worker-default deploy/chatbot deploy/polyphemus
```

Deployment names are `backend`, `chatbot`, `docs`, `frontend`, `otel-collector`, `polyphemus`,
`telemetry-processor`, `worker-default`. Every one receives `rhesis-app-secrets` via `envFrom`,
but only the four above call Vertex. `apps/worker` has no model references of its own, yet it
imports `rhesis.backend.worker` and runs `rhesis.backend.jobs.*`, so it executes the backend's
Vertex code and must be restarted.

Expect this to be slow on a busy cluster: on stg the restart triggered a node scale-up and an
8 minute image pull. Old pods keep serving throughout, so that is slow rather than an outage.

Then check **every pod**, not `kubectl exec deploy/<name>`. That form picks a single pod, and on
2026-09-03 it hit a fresh one while a pod from the previous ReplicaSet was still serving the old
credential — the rollout looked complete when a third of requests were still failing:

```bash
for p in $(kubectl --context="${CTX}" -n rhesis get pods -o name | sed 's|pod/||' \
           | grep -E "^(backend|worker-default|chatbot|polyphemus)-"); do
  printf "%-34s " "$p"
  kubectl --context="${CTX}" -n rhesis exec "$p" -- printenv GOOGLE_APPLICATION_CREDENTIALS 2>/dev/null \
    | python3 -c "import sys,base64,json; d=json.loads(base64.b64decode(sys.stdin.read().strip(),validate=True)); print(d['client_email'].split('@')[0],'->',d['project_id'])"
done
```

### 6. Verify, then move on

First check for the failure this whole sequence guards against. A non-zero count here, with the
**old** project in the message, means the credential and `VERTEX_AI_PROJECT` disagree: step 2a was
skipped, or the chart change is not deployed:

```bash
kubectl --context="${CTX}" -n rhesis logs deploy/backend --since=5m --tail=400 \
  | grep -c "aiplatform.endpoints.predict"     # must be 0
```

Then confirm traffic moved. The authoritative signal is the metric
`aiplatform.googleapis.com/publisher/online_serving/model_invocation_count` in the **new** project
starting to record invocations while the old project's goes quiet. Billing export confirms it a
day later.

These workloads are bursty and idle for long stretches, so an empty metric is not evidence of
failure — wait for a burst. The stronger immediate signal is the per-pod check in step 5, since
env vars are fixed at pod start: if every pod holds the new credential, nothing can reach the old
project regardless of what the metric has recorded yet.

## Rollback

**Do not use `gcloud secrets versions disable`.** Secret Manager's `latest` points at the
highest version *number* regardless of state, so disabling the version you just added does not
fall back to the previous one: it makes the secret unreadable.

```
gcloud secrets versions disable 2   ->  2 disabled, 1 enabled
gcloud secrets versions access latest
    ERROR: FAILED_PRECONDITION: Secret Version [...] 
```

Destroying the version does not help either; `latest` still resolves to it. An earlier version
of this README claimed `latest` skipped disabled versions and recommended `disable` as a
one-command rollback. That was wrong, and following it during the 2026-09-03 prd incident turned a
broken credential into an unreadable secret.

Roll back by adding a **new** version holding the old value, copied from the last known-good
version so the key never touches disk:

```bash
ENV=dev
PROJECT=rhesis-dev-494712
S="${ENV}-rhesis-google-application-credentials"
GOOD=<last known-good version number>

gcloud secrets versions access "${GOOD}" --secret="$S" --project="$PROJECT" \
  | tr -d '\n' \
  | gcloud secrets versions add "$S" --project="$PROJECT" --data-file=-
# then force-sync and restart as in step 5
```

No chart revert is needed, because the project follows the key.

Do **not** disable `aiplatform.googleapis.com` in `playground-437609` as a rollback step.
That is what caused the 2026-09-02 outage: all three environments authenticate into that
project until their rotation is done, so toggling the API there takes down dev, stg and prd
at once.

## Follow-up: drop the keys entirely

Workload Identity would remove the JSON keys, as `modules/cnpg-barman-sa-gcp` already does.
Two things block it:

1. The chart sets no `serviceAccountName` and defines no `ServiceAccount`, so every pod runs
   as the namespace `default` KSA. Binding that would grant Vertex access to all eight
   components, so per-component KSAs are needed first.
2. `sdk/src/rhesis/sdk/models/providers/vertex_ai.py` raises when
   `GOOGLE_APPLICATION_CREDENTIALS` is unset instead of falling back to ADC. LiteLLM
   underneath does support ADC, so the change is small but it is a code change.
