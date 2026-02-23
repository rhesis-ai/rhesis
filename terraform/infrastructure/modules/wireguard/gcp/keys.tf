# Key generation data sources run on every plan/apply but their values are only
# consumed on the FIRST creation of the terraform_data resources below.
data "external" "server_key_gen" {
  program = ["bash", "-c", "priv=$(wg genkey); pub=$(echo \"$priv\" | wg pubkey); jq -n --arg p \"$priv\" --arg b \"$pub\" '{private_key: $p, public_key: $b}'"]
}

data "external" "peer_key_gen" {
  for_each = { for p in var.wireguard_peers : p.identifier => p }
  program  = ["bash", "-c", "priv=$(wg genkey); pub=$(echo \"$priv\" | wg pubkey); jq -n --arg p \"$priv\" --arg b \"$pub\" '{private_key: $p, public_key: $b}'"]
}

# Keys are captured in terraform state on first creation and never rotated by a
# subsequent plan/apply. To rotate keys intentionally, delete these resources
# from state and re-apply: terraform state rm module.wireguard_server.terraform_data.server_key
resource "terraform_data" "server_key" {
  lifecycle {
    ignore_changes = all
  }

  input = {
    private_key = data.external.server_key_gen.result.private_key
    public_key  = data.external.server_key_gen.result.public_key
  }
}

resource "terraform_data" "peer_keys" {
  for_each = { for p in var.wireguard_peers : p.identifier => p }

  lifecycle {
    ignore_changes = all
  }

  input = {
    private_key = data.external.peer_key_gen[each.key].result.private_key
    public_key  = data.external.peer_key_gen[each.key].result.public_key
  }
}
