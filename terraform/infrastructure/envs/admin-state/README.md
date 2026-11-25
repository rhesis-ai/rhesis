# envs/admin-state

Manages the GCS bucket that holds every environment's Terraform state
(`rhesis-platform-admin-tfstate`), plus the data-access audit logging for it.

The bucket was created by hand at bootstrap and was unmanaged until this root. The
`import` block in `main.tf` adopts it; after the first successful apply the block can be
deleted.

## What this root sets

- **Versioning on**, with a lifecycle rule keeping a bounded number of superseded versions
  and ageing out old ones. This is the rollback path for a bad apply or a mistaken
  `terraform state rm`.
- **Public access prevention enforced**, uniform bucket-level access on (already set).
- **Per-env IAM.** Each env's Terraform SA can write only its own state prefix under
  `terraform/infrastructure/envs/<env>/`, and read only the prefixes its root consumes via
  `terraform_remote_state`:
  - `terraform-dev` writes `dev`, reads `wireguard`
  - `terraform-stg` writes `stg`, reads `wireguard` and `prd`
  - `terraform-prd` writes `prd`
  - `terraform-wireguard` (the admin SA) holds `storage.admin` on the bucket: it manages
    the bucket and runs the `wireguard`, `billing` and `admin-state` roots, and reads
    `dev`/`stg`/`prd` remote state.
  This replaces the earlier bucket-wide `objectAdmin` each SA carried with access scoped to
  the prefixes each root actually uses.
- **Data-access audit logs** (`DATA_READ`/`DATA_WRITE`) for `storage.googleapis.com` in the
  admin project.

## Bootstrap grants (out of band, once)

Like `envs/billing`, this root's runner needs rights it did not have before it could
manage these resources. The authoritative IAM policy cannot be set by an SA that lacks
`setIamPolicy`, so grant these to `terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com`
before the first plan, then this root keeps them as code:

- `roles/storage.admin` on the bucket (manage bucket settings and IAM):
  ```
  gcloud storage buckets add-iam-policy-binding gs://rhesis-platform-admin-tfstate \
    --member=serviceAccount:terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com \
    --role=roles/storage.admin
  ```
- `roles/resourcemanager.projectIamAdmin` on `rhesis-platform-admin` (edit the project IAM
  policy for the audit config). This is the one broad grant this root needs; if it is not
  acceptable to hold it on a CI SA long-term, set the audit config once by hand and drop
  the `google_project_iam_audit_config` resource from this root.

## Legacy state objects to remove

Two objects from the old (pre-`infrastructure/envs`) layout still sit in the bucket and are
dead:

```
terraform/environments/dev/default.tfstate   (2025-05-15)
terraform/environments/stg/default.tfstate   (2025-05-16)
```

They are not Terraform-managed, so this root does not touch them. Back up and delete them
out of band once this root is in:

```
gcloud storage cp gs://rhesis-platform-admin-tfstate/terraform/environments/dev/default.tfstate  ./backup/
gcloud storage cp gs://rhesis-platform-admin-tfstate/terraform/environments/stg/default.tfstate  ./backup/
gcloud storage rm gs://rhesis-platform-admin-tfstate/terraform/environments/dev/default.tfstate
gcloud storage rm gs://rhesis-platform-admin-tfstate/terraform/environments/stg/default.tfstate
```

## Running

Manual dispatch only (excluded from the automatic plan matrix, like `wireguard`/`admin`):

```
gh workflow run terraform-infrastructure.yml -R rhesis-ai/rhesis \
  -f environment=admin-state -f action=plan
```

Then `-f action=apply` once the plan looks right. The first plan must run after the
bootstrap grants above are in place.
