[Interface]
PrivateKey = ${peer_private_key}
Address = ${peer_ip}/32

[Peer]
PublicKey = ${server_public_key}
Endpoint = ${server_endpoint}
AllowedIPs = ${allowed_ips}
PersistentKeepalive = 25
