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
## Data-access audit logging (out of band, once)

`DATA_READ`/`DATA_WRITE` audit logging for `storage.googleapis.com` is enabled on the admin
project by a project owner, not by this root: it is a project-IAM-policy edit that would
need `projectIamAdmin` on the CI SA, which is broader than this root should hold. It changes
rarely, so it is a one-time setting.

## Bootstrap grant (out of band, once)

Like `envs/billing`, this root's runner needs a right it cannot grant itself: the
authoritative bucket IAM policy cannot be set by an SA that lacks `setIamPolicy`. Grant this
to `terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com` before the first
plan, then this root keeps it as code:

- `roles/storage.admin` on the bucket (manage bucket settings and IAM):
  ```
  gcloud storage buckets add-iam-policy-binding gs://rhesis-platform-admin-tfstate \
    --member=serviceAccount:terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com \
    --role=roles/storage.admin
  ```

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
