# Monitoring stack prerequisites

## Service names and ports (validation)

Grafana, Alloy, and the Grafana datasources assume the following Services exist in the **`monitoring`** namespace (from the kube-prometheus-stack, Loki, and Grafana Operator chart defaults). After deploy, confirm:

```bash
kubectl -n monitoring get svc \
  grafana-service kube-prometheus-stack-prometheus loki-gateway -o wide
```

- **Grafana (operator):** `grafana-service:3000` (Service name is `{Grafana metadata.name}-service`, see [Grafana operator](https://grafana.github.io/grafana-operator/docs/grafana/))
- **Prometheus (kube-prometheus-stack):** `kube-prometheus-stack-prometheus:9090`
- **Loki (SingleBinary + chart gateway):** `loki-gateway:80` — the Loki chart keeps `gateway.enabled: true` by default; the gateway nginx forwards to the single-binary pods. The Service name is `<Helm release name>-gateway` (the Argo Application/Helm release is named `loki`, so the Service is `loki-gateway`)

## Grafana admin password (GCP Secret Manager)

Before syncing `dev-grafana-operator` (and stg/prd equivalents), create a Secret Manager secret named **`grafana-admin-password`** in each GCP project. The secret must contain the Grafana `admin` user password as **plain text** (the ExternalSecret maps it to key `admin-password` in Kubernetes).

**Example (dev project `rhesis-dev`):**

```bash
echo -n 'your-secure-password' | gcloud secrets create grafana-admin-password \
  --project=rhesis-dev \
  --data-file=-
```

To add a new version to an existing secret:

```bash
echo -n 'your-secure-password' | gcloud secrets versions add grafana-admin-password \
  --project=rhesis-dev \
  --data-file=-
```

Repeat for each environment’s GCP project used by External Secrets Operator.

## Grafana alert notifications (Discord webhook)

Before syncing `{dev,stg,prd}-grafana-resources`, create a Secret Manager secret named
**`{dev,stg,prd}-grafana-discord-webhook`** in the matching GCP project, containing that
env's Discord incoming webhook URL as plain text (the ExternalSecret maps it to key `url`
in Kubernetes). Each env's secret can point at the same Discord channel or a different one —
nothing else needs to change either way.

```bash
echo -n 'https://discord.com/api/webhooks/...' | gcloud secrets create dev-grafana-discord-webhook \
  --project=rhesis-dev \
  --data-file=-
```

Repeat with `stg-grafana-discord-webhook` / `prd-grafana-discord-webhook` in the `rhesis-stg-494712` /
`rhesis-prd` projects.

Alert emails need no new secret: `grafana-smtp-credentials.yaml` in each cluster's
`grafana-resources` overlay reuses the same `{dev,stg,prd}-rhesis-smtp-*` GSM keys the
app already uses for its own SMTP (`external-secrets/rhesis-app-secrets.yaml`), synced
separately into `monitoring`. The sender address (`GF_SMTP_FROM_ADDRESS`) is a plain
literal in `grafana-instance.yaml` instead, not from the app's `FROM_EMAIL` secret —
that value is formatted as `"Display Name" <hello@rhesis.ai>` for the app's email
library, which Grafana's from_address field rejects.

## Grafana TLS (cert-manager / Let’s Encrypt)

The Grafana `Ingress` uses `cert-manager.io/cluster-issuer: letsencrypt-prod` and the **internal** NGINX class for user traffic. cert-manager still completes **HTTP-01** using the solver in `ClusterIssuer` (typically a separate **external**-class `Ingress` in the same namespace). While issuance is in progress, the `Certificate` condition often reads **Issuing certificate as Secret does not exist**—that only means the final `grafana-tls` secret is not ready yet.

The Grafana ingress sets **`cert-manager.io/issue-temporary-certificate: "true"`** so a temporary cert is written to `grafana-tls` immediately; Argo CD Ingress health improves while Let’s Encrypt finishes.

If the `Certificate` stays **Issuing** for a long time:

```bash
kubectl -n monitoring describe certificate grafana-tls
kubectl -n monitoring get challenges.acme.cert-manager.io -o wide
kubectl -n monitoring get ingress
```

Confirm **external-dns** (Cloudflare) creates a public record for `grafana.<env>.rhesis.ai` from the **solver** ingress, and that HTTP-01 can complete from the internet. If the hostname is only resolvable on the VPN, switch the issuer to **DNS-01** (for example Cloudflare) instead of HTTP-01.
