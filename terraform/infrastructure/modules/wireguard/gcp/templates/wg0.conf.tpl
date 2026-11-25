[Interface]
# Use /32 to avoid route conflict: VM's primary NIC already has 10.0.0.0/24 (VPC subnet).
# wg-quick would add 10.0.0.0/24 via wg0 → "RTNETLINK answers: File exists". Peer traffic still uses peer_cidr (AllowedIPs).
Address = ${server_ip}/32
ListenPort = ${listen_port}
# The private key never leaves the VM: server-key.sh generates it in place.
PostUp = wg set %i private-key /etc/wireguard/server.key

# NAT masquerading for VPN clients
PostUp = iptables -t nat -A POSTROUTING -s ${peer_cidr} -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s ${peer_cidr} -j MASQUERADE

# Clamp forwarded TCP MSS to fit the tunnel. The GCP NIC is MTU 1460; WireGuard adds
# 60 bytes, so the largest inner packet that fits is 1400 (MSS 1360). wg0 defaults to
# 1420, so env responses (GKE/LB at 1460) oversize the tunnel and blackhole: TCP
# connects but TLS stalls. A fixed MSS is required here, not --clamp-mss-to-pmtu, which
# only sees wg0's own 1420 and clamps to 1380 (still too big). SYN,RST SYN matches both
# the SYN and the SYN-ACK, so both directions are capped regardless of client MTU. 1340
# leaves ~20 bytes of margin for any extra encapsulation on the path. The tcpmss match
# (1341:65535) makes this clamp downward only, so a client already on a smaller MTU keeps
# its lower MSS instead of being raised back up into the blackhole.
PostUp = iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -m tcpmss --mss 1341:65535 -j TCPMSS --set-mss 1340
PostDown = iptables -t mangle -D FORWARD -p tcp --tcp-flags SYN,RST SYN -m tcpmss --mss 1341:65535 -j TCPMSS --set-mss 1340

# Allow VPN clients to reach the server itself (e.g. ping 10.0.0.1)
PostUp = iptables -A INPUT -s ${peer_cidr} -j ACCEPT
PostDown = iptables -D INPUT -s ${peer_cidr} -j ACCEPT

# Per-peer access control rules
%{ for peer in peers }
%{ for subnet in peer.subnets }
# Allow ${peer.identifier} to ${subnet} environment
PostUp = iptables -A FORWARD -s ${peer.ip}/32 -d ${subnet_cidrs[subnet]} -j ACCEPT
PostDown = iptables -D FORWARD -s ${peer.ip}/32 -d ${subnet_cidrs[subnet]} -j ACCEPT
%{ if contains(keys(gke_public_endpoints), subnet) }
# Allow ${peer.identifier} to ${subnet} GKE public endpoint
PostUp = iptables -A FORWARD -s ${peer.ip}/32 -d ${gke_public_endpoints[subnet]}/32 -j ACCEPT
PostDown = iptables -D FORWARD -s ${peer.ip}/32 -d ${gke_public_endpoints[subnet]}/32 -j ACCEPT
%{ endif }
%{ endfor }
# Explicit DROP for any other traffic from ${peer.identifier}
PostUp = iptables -A FORWARD -s ${peer.ip}/32 -j DROP
PostDown = iptables -D FORWARD -s ${peer.ip}/32 -j DROP
%{ endfor }

# Peer definitions
%{ for peer in peers }
[Peer]
# ${peer.identifier}
PublicKey = ${peer.public_key}
AllowedIPs = ${peer.ip}/32

%{ endfor }
