# Monitoring stack prerequisites

## Grafana admin password (GCP Secret Manager)

Before syncing `dev-grafana-operator` (and stg/prd equivalents), create a Secret Manager secret named **`grafana-admin-password`** in each GCP project. The secret must contain the Grafana `admin` user password as **plain text** (the ExternalSecret maps it to key `admin-password` in Kubernetes).

**Example (dev project `rhesis-dev-sandbox`):**

```bash
echo -n 'your-secure-password' | gcloud secrets create grafana-admin-password \
  --project=rhesis-dev-sandbox \
  --data-file=-
```

To add a new version to an existing secret:

```bash
echo -n 'your-secure-password' | gcloud secrets versions add grafana-admin-password \
  --project=rhesis-dev-sandbox \
  --data-file=-
```

Repeat for each environment’s GCP project used by External Secrets Operator.
