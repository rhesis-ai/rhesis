# text-moderation/gcp

Enables Google Cloud Natural Language (`language.googleapis.com`) and the API Keys API in an
environment's project. The backend's toxicity metric calls `documents:moderateText` on the EU
endpoint (`eu-language.googleapis.com`) with `GOOGLE_MODERATION_API_KEY`.

## Why

Perspective API shuts down on 2026-12-31, and Google names no successor. `moderateText` is
the closest Google service: plain text in, a 0-1 confidence per category out. Its `Toxic`
category replaces Perspective's `TOXICITY`. Without a key, the metric falls back to the judge
model, so self-hosted installs don't need any of this.

## Key runbook

Terraform does not create the key, because `google_apikeys_key` would put it in state.
Run once per environment, in the order dev, stg, prd.

**Publish the key before the cluster's ExternalSecret lists it.** External Secrets fails the
whole `rhesis-app-secrets` sync when one `remoteRef` is missing, so no other secret change
reaches that cluster until the key exists. The key only needs `apikeys.googleapis.com` to be
created, and `language.googleapis.com` to be called; enable both first if the Terraform has
not been applied yet.

```bash
ENV=dev
PROJECT=rhesis-dev-494712

# 1. Create a key that can only call Natural Language.
gcloud services api-keys create --project="$PROJECT" \
  --display-name="rhesis-${ENV}-text-moderation" \
  --api-target=service=language.googleapis.com

# 2. Confirm moderateText answers on the EU endpoint. The docs only promise it for AU,
#    so do not skip this. Expect a moderationCategories list, not a 404 or 403.
KEY_NAME=$(gcloud services api-keys list --project="$PROJECT" \
  --filter="displayName=rhesis-${ENV}-text-moderation" --format="value(name)")
KEY=$(gcloud services api-keys get-key-string "$KEY_NAME" --format="value(keyString)")
curl -s -X POST "https://eu-language.googleapis.com/v2/documents:moderateText" \
  -H "x-goog-api-key: ${KEY}" -H "Content-Type: application/json" \
  -d '{"document":{"type":"PLAIN_TEXT","content":"You are an idiot."}}'

# 3. Put it in infrastructure/config/gsm-secrets.json as .<env>.GOOGLE_MODERATION_API_KEY,
#    then publish it to Secret Manager. External Secrets syncs it into rhesis-app-secrets.
./infrastructure/config/gsm-secrets-sync.sh --project "$PROJECT" --json-env "$ENV" \
  --secret-key GOOGLE_MODERATION_API_KEY
```
