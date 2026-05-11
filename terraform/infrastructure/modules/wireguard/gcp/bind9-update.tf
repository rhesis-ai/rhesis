# Live BIND9 config update — pushes named.conf changes to the running VM
# without recreating it. Cloud-init handles first-boot setup; this resource
# handles all subsequent config changes (new TSIG keys, ACL changes).
#
# How it works:
#   1. Terraform detects that named.conf content has changed (via SHA hash trigger)
#   2. Provisioner pushes the new config to the VM through IAP
#   3. Config is written atomically: decode → validate (named-checkconf) → rename
#      into place. The live named.conf is never truncated before validation passes,
#      so a flaky connection or bad content cannot leave an empty/corrupt config.
#
# Note: Zone file is NOT overwritten on update to preserve dynamic records.
# If the zone file is missing (e.g. first run with bind9_config_update before
# cloud-init wrote it), it is seeded from the template before named starts.

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

      # Verify the local temp file is non-empty before transferring
      if [ ! -s "$tmpfile" ]; then
        echo "ERROR: base64-encoded named.conf is empty — aborting to protect live config"
        exit 1
      fi

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

      # Remove any stale file from a previous failed run.
      # Uses named.conf.tf.b64 (not named.conf.b64) to avoid colliding with
      # the identically-named temp file that cloud-init writes during first boot.
      gcloud_retry gcloud compute ssh wireguard-server \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap \
        --command="sudo rm -f /tmp/named.conf.tf.b64 /tmp/named.conf.new" 2>/dev/null || true

      # Copy base64-encoded config to server
      gcloud_retry gcloud compute scp "$tmpfile" wireguard-server:/tmp/named.conf.tf.b64 \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap

      # Atomic config update on the VM:
      #   1. Decode into a staging file (/tmp/named.conf.new) — never touching the live config
      #   2. Guard: reject empty decode result
      #   3. Validate the staging file with named-checkconf
      #   4. Only then atomically replace the live named.conf
      #   5. Seed zone file if missing (preserves dynamic records when it already exists)
      #   6. Restart named
      gcloud_retry gcloud compute ssh wireguard-server \
        --zone="$ZONE" --project="$PROJECT" \
        --tunnel-through-iap \
        --command="sudo bash -c '\
          set -e && \
          apt-get install -y -qq bind9 > /dev/null 2>&1 || true && \
          systemctl stop dnsmasq 2>/dev/null || true && \
          systemctl disable dnsmasq 2>/dev/null || true && \
          base64 -d /tmp/named.conf.tf.b64 > /tmp/named.conf.new && \
          rm /tmp/named.conf.tf.b64 && \
          [ -s /tmp/named.conf.new ] || { echo \"ERROR: decoded named.conf is empty\"; rm -f /tmp/named.conf.new; exit 1; } && \
          named-checkconf /tmp/named.conf.new && \
          mv /tmp/named.conf.new /etc/bind/named.conf && \
          mkdir -p /var/lib/bind && \
          chown -R bind:bind /var/lib/bind && \
          if [ ! -f /var/lib/bind/rhesis.ai.zone ]; then \
            printf %s ${base64encode(local.bind9_rhesis_ai_zone_file)} | base64 -d > /var/lib/bind/rhesis.ai.zone && \
            chown bind:bind /var/lib/bind/rhesis.ai.zone; \
          fi && \
          systemctl enable named && \
          systemctl restart named && \
          echo \"BIND9 config updated and reloaded successfully\"'"
    EOT
  }

  depends_on = [google_compute_instance.wireguard]
}
