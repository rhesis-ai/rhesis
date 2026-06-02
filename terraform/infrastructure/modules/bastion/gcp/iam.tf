# Grant each member the ability to open an IAP tunnel to this specific instance.
resource "google_iap_tunnel_instance_iam_member" "iap_access" {
  for_each = toset(var.iap_members)

  project  = var.project_id
  zone     = var.zone
  instance = google_compute_instance.bastion.name
  role     = "roles/iap.tunnelResourceAccessor"
  member   = each.value

  depends_on = [google_compute_instance.bastion]
}

# OS Login: allows members to SSH in via their Google identity.
# roles/compute.osLogin  → non-root SSH
# roles/compute.osAdminLogin → sudo access (use if kubectl needs root)
resource "google_project_iam_member" "oslogin" {
  for_each = toset(var.iap_members)

  project = var.project_id
  role    = "roles/compute.osLogin"
  member  = each.value
}
