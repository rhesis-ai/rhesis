# Live BIND9 config update — pushes named.conf changes to the running VM
# without recreating it. Cloud-init handles first-boot setup; this resource
# handles all subsequent config changes (new TSIG keys, ACL changes).
#
# How it works:
#   1. Terraform detects that named.conf content has changed (via SHA hash trigger)
#   2. Provisioner pushes the new config to the VM through IAP
#   3. Restarts named service to apply changes
#
# Note: Zone file is NOT overwritten on update to preserve dynamic records.
# Only named.conf (TSIG keys, ACLs, options) is updated.

resource "terraform_data" "bind9_config_update" {
  count = length(var.bind9_tsig_keys) > 0 ? 1 : 0

  # Re-provision whenever the rendered BIND9 config changes
  triggers_replace = sha256(local.bind9_named_conf)

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -e

      ZONE="${var.region}-a"
      PROJECT="${var.project_id}"

      # Write base64 config to a temp file
      tmpfile=$(mktemp)
      trap 'rm -f "$tmpfile"' EXIT
      printf '%s' '${base64encode(local.bind9_named_conf)}' > "$tmpfile"

      # Wait for VM to accept SSH
      for i in $(seq 1 30); do
        if gcloud compute ssh wireguard-server \
          --zone="$ZONE" --project="$PROJECT" \
          --tunnel-through-iap \
          --command="true" 2>/dev/null; then
          break
        fi
        echo "Waiting for SSH (attempt $i/30)..."
        sleep 10
      done

      # Remove any stale file from a previous failed run
      gcloud compute ssh wireguard-server \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap \
        --command="sudo rm -f /tmp/named.conf.b64" 2>/dev/null || true

      # Copy base64-encoded config to server
      gcloud compute scp "$tmpfile" wireguard-server:/tmp/named.conf.b64 \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap

      # Decode config, install bind9 if needed, restart named
      gcloud compute ssh wireguard-server \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap \
        --command="sudo bash -c '\
          apt-get install -y -qq bind9 > /dev/null 2>&1 || true && \
          systemctl stop dnsmasq 2>/dev/null || true && \
          systemctl disable dnsmasq 2>/dev/null || true && \
          base64 -d /tmp/named.conf.b64 > /etc/bind/named.conf && \
          rm /tmp/named.conf.b64 && \
          mkdir -p /var/lib/bind && \
          chown -R bind:bind /var/lib/bind && \
          named-checkconf && \
          systemctl enable named && \
          systemctl restart named && \
          echo \"BIND9 config updated and reloaded successfully\"'"
    EOT
  }

  depends_on = [google_compute_instance.wireguard]
}
