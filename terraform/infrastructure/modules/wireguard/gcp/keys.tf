# WireGuard key pairs using the wireguard provider (idempotent, no local tooling needed).
# Keys are generated once on creation and stored in Terraform state.
# To rotate keys intentionally: terraform taint module.wireguard_server.wireguard_asymmetric_key.server

resource "wireguard_asymmetric_key" "server" {}

resource "wireguard_asymmetric_key" "peers" {
  for_each = { for p in var.wireguard_peers : p.identifier => p }
}
