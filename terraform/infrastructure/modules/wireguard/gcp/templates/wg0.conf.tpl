[Interface]
Address = ${server_ip}/24
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
