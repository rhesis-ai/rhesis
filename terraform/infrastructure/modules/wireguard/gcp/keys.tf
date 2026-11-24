# No private keys in Terraform: each peer generates its own key pair and supplies the
# public key, and the server generates its private key on the VM (server-key.sh.tpl).
# The wireguard provider stays declared only so Terraform can drop the old
# wireguard_asymmetric_key resources from state; remove it once that has applied.
