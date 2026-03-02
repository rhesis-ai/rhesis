# Live WireGuard config update — pushes peer/iptables changes to the running VM
# without recreating it. Cloud-init handles first-boot setup; this resource
# handles all subsequent config changes (new peers, removed peers, ACL changes).
#
# How it works:
#   1. Terraform detects that wg0.conf content has changed (via SHA hash trigger)
#   2. Provisioner SCPs the new config to the VM through IAP
#   3. Restarts wg-quick@wg0 which re-runs PostUp/PostDown iptables rules
#
# Impact: connected VPN users experience a brief (~2s) interruption during restart.
# To avoid even that, consider `wg syncconf` (but it cannot update iptables rules).

resource "terraform_data" "wireguard_config_update" {
  # Re-provision whenever the rendered WireGuard config changes
  triggers_replace = sha256(local.wireguard_config)

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -e

      ZONE="${var.region}-a"
      PROJECT="${var.project_id}"

      # Write base64 config to a temp file (avoids shell argument length limits)
      tmpfile=$(mktemp)
      trap 'rm -f "$tmpfile"' EXIT
      printf '%s' '${base64encode(local.wireguard_config)}' > "$tmpfile"

      # Wait for VM to accept SSH (cloud-init may still be running on first apply)
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

      # Copy base64-encoded config to server
      gcloud compute scp "$tmpfile" wireguard-server:/tmp/wg0.b64 \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap

      # Decode config, set permissions, reload WireGuard
      gcloud compute ssh wireguard-server \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap \
        --command="sudo bash -c '\
          base64 -d /tmp/wg0.b64 > /etc/wireguard/wg0.conf && \
          chmod 600 /etc/wireguard/wg0.conf && \
          rm /tmp/wg0.b64 && \
          systemctl restart wg-quick@wg0 && \
          echo \"WireGuard config updated and reloaded successfully\"'"
    EOT
  }

  depends_on = [google_compute_instance.wireguard]
}
