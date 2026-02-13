# WireGuard key generation using wg genkey (random_password is not valid WireGuard format)

# Generate server key pair via wg genkey
data "external" "server_key" {
  program = ["bash", "-c", "priv=$(wg genkey); pub=$(echo \"$priv\" | wg pubkey); jq -n --arg p \"$priv\" --arg b \"$pub\" '{private_key: $p, public_key: $b}'"]
}

# Generate peer key pairs via wg genkey (one per peer)
data "external" "peer_keys" {
  for_each = { for p in var.wireguard_peers : p.identifier => p }
  program  = ["bash", "-c", "priv=$(wg genkey); pub=$(echo \"$priv\" | wg pubkey); jq -n --arg p \"$priv\" --arg b \"$pub\" '{private_key: $p, public_key: $b}'"]
}
