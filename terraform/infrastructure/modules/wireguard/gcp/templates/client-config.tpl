[Interface]
PrivateKey = <your private key: the one you generated, never shared>
Address = ${peer_ip}/32
DNS = ${server_tunnel_ip}

[Peer]
PublicKey = ${server_public_key}
Endpoint = ${server_endpoint}
AllowedIPs = ${allowed_ips}
PersistentKeepalive = 25
