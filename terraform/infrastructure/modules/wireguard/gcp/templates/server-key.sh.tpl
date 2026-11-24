#!/bin/bash
# Generates the WireGuard server private key on the VM so it never reaches Terraform.
set -euo pipefail
dir=/etc/wireguard
install -d -m 700 "$dir"
if [ ! -s "$dir/server.key" ] || [ "$(cat "$dir/server.key.rotation" 2>/dev/null)" != "${rotation}" ]; then
  (umask 077 && wg genkey > "$dir/server.key.new" && mv "$dir/server.key.new" "$dir/server.key")
  printf '%s' "${rotation}" > "$dir/server.key.rotation"
fi
