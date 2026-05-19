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

      ZONE="${google_compute_instance.wireguard.zone}"
      PROJECT="${var.project_id}"

      # Write base64 config to a temp file (avoids shell argument length limits)
      tmpfile=$(mktemp)
      trap 'rm -f "$tmpfile"' EXIT
      printf '%s' '${base64encode(local.wireguard_config)}' > "$tmpfile"

      # OS Login issues a fresh short-lived SSH certificate on every gcloud call.
      # Transient API hiccups or propagation delays on a newly created VM can cause
      # individual calls to fail even after an earlier call succeeded. This helper
      # retries any gcloud ssh/scp command up to 10 times with a 10-second backoff.
      gcloud_retry() {
        local attempt
        for attempt in $(seq 1 10); do
          if "$@"; then
            return 0
          fi
          echo "SSH/SCP failed (attempt $attempt/10), retrying in 10s..."
          sleep 10
        done
        echo "ERROR: command failed after 10 attempts: $*"
        return 1
      }

      # Wait for VM to accept SSH and cloud-init to finish
      # (first apply: cloud-init installs wireguard and creates /etc/wireguard/)
      for i in $(seq 1 60); do
        if gcloud compute ssh wireguard-server \
          --zone="$ZONE" --project="$PROJECT" \
          --tunnel-through-iap \
          --command="true" 2>/dev/null; then
          break
        fi
        echo "Waiting for SSH (attempt $i/60)..."
        sleep 10
      done

      echo "Waiting for cloud-init to finish..."
      gcloud_retry gcloud compute ssh wireguard-server \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap \
        --command="sudo cloud-init status --wait" || true

      # Remove any stale file from a previous failed run (may be owned by root)
      gcloud_retry gcloud compute ssh wireguard-server \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap \
        --command="sudo rm -f /tmp/wg0.b64" 2>/dev/null || true

      # Copy base64-encoded config to server via SSH stdin pipe.
      # gcloud compute scp crashes on some gcloud/Python versions with
      # TypeError: quote_from_bytes() expected bytes — use ssh+stdin instead.
      for scp_attempt in $(seq 1 10); do
        if cat "$tmpfile" | gcloud compute ssh wireguard-server \
          --zone="$ZONE" --project="$PROJECT" \
          --tunnel-through-iap \
          --command="cat > /tmp/wg0.b64"; then
          break
        fi
        if [ "$scp_attempt" = "10" ]; then
          echo "ERROR: config upload failed after 10 attempts"
          exit 1
        fi
        echo "SSH upload failed (attempt $scp_attempt/10), retrying in 10s..."
        sleep 10
      done

      # Decode config, set permissions, reload WireGuard
      gcloud_retry gcloud compute ssh wireguard-server \
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
