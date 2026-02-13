#cloud-config
package_update: true
package_upgrade: true
packages:
  - wireguard
  - wireguard-tools
  - iptables
  - dnsmasq

write_files:
  - path: /etc/sysctl.d/99-wireguard.conf
    content: |
      net.ipv4.ip_forward=1
  - path: /tmp/wg0.b64
    content: "${wireguard_config_b64}"
    permissions: '0600'

runcmd:
  - mkdir -p /etc/wireguard && base64 -d /tmp/wg0.b64 > /etc/wireguard/wg0.conf && chmod 600 /etc/wireguard/wg0.conf && rm /tmp/wg0.b64
  - sysctl -p /etc/sysctl.d/99-wireguard.conf
  - systemctl enable wg-quick@wg0
  - systemctl start wg-quick@wg0
  - sed -i 's/^[#]*DNSStubListener=.*/DNSStubListener=no/' /etc/systemd/resolved.conf
  - systemctl restart systemd-resolved
  - systemctl enable dnsmasq
  - systemctl start dnsmasq
