[Interface]
# Use /32 to avoid route conflict: VM's primary NIC already has 10.0.0.0/24 (VPC subnet).
# wg-quick would add 10.0.0.0/24 via wg0 → "RTNETLINK answers: File exists". Peer traffic still uses peer_cidr (AllowedIPs).
Address = ${server_ip}/32
ListenPort = ${listen_port}
PrivateKey = ${server_private_key}

# NAT masquerading for VPN clients
PostUp = iptables -t nat -A POSTROUTING -s ${peer_cidr} -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s ${peer_cidr} -j MASQUERADE

# Allow VPN clients to reach the server itself (e.g. ping 10.0.0.1)
PostUp = iptables -A INPUT -s ${peer_cidr} -j ACCEPT
PostDown = iptables -D INPUT -s ${peer_cidr} -j ACCEPT

# Per-peer access control rules
%{ for peer in peers }
%{ for subnet in peer.subnets }
# Allow ${peer.identifier} to ${subnet} environment
PostUp = iptables -A FORWARD -s ${peer.ip}/32 -d ${subnet_cidrs[subnet]} -j ACCEPT
PostDown = iptables -D FORWARD -s ${peer.ip}/32 -d ${subnet_cidrs[subnet]} -j ACCEPT
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
