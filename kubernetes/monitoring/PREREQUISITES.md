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
