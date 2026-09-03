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

### 2. Check the models exist in the new project

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

```bash
CTX=connectgateway_rhesis-dev-494712_global_dev
kubectl --context="${CTX}" -n rhesis annotate externalsecret rhesis-app-secrets \
  force-sync="$(date +%s)" --overwrite
kubectl --context="${CTX}" -n rhesis rollout restart \
  deploy/backend deploy/worker-default deploy/chatbot deploy/polyphemus
```

Deployment names are `backend`, `chatbot`, `docs`, `frontend`, `otel-collector`, `polyphemus`,
`telemetry-processor`, `worker-default`. Every one of them receives `rhesis-app-secrets` via
`envFrom`, but only the four above are expected to call Vertex; confirm against the new
project's invocation metric and widen the restart if any traffic is missing.

### 6. Verify, then move on

Confirm calls now bill to the new project and are succeeding:

```bash
gcloud logging read 'protoPayload.serviceName="aiplatform.googleapis.com"' \
  --project="${PROJECT}" --freshness=15m --limit=5
```

The authoritative signal is the metric
`aiplatform.googleapis.com/publisher/online_serving/model_invocation_count` in the **new**
project starting to record invocations while the old project's goes quiet. Billing export
confirms it a day later.

## Rollback

One command, because the project follows the key. Secret Manager's `latest` resolves to the
newest *enabled* version, so disabling the version you just added reverts to the previous
key, and the project reverts with it:

```bash
ENV=dev
PROJECT=rhesis-dev-494712
gcloud secrets versions disable <new-version> \
  --secret="${ENV}-rhesis-google-application-credentials" --project="${PROJECT}"
# then force-sync and restart as in step 5
```

No need to re-upload the old key, and no chart revert.

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
