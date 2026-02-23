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
  - path: /tmp/gke-routing.b64
    content: "${gke_routing_script_b64}"
    permissions: '0600'
  - path: /etc/systemd/system/gke-routing.service
    content: |
      [Unit]
      Description=GKE master routing setup
      After=network-online.target
      Wants=network-online.target

      [Service]
      Type=oneshot
      ExecStart=/usr/local/bin/gke-routing-setup.sh
      RemainAfterExit=yes

      [Install]
      WantedBy=multi-user.target

runcmd:
  - mkdir -p /etc/wireguard && base64 -d /tmp/wg0.b64 > /etc/wireguard/wg0.conf && chmod 600 /etc/wireguard/wg0.conf && rm /tmp/wg0.b64
  - base64 -d /tmp/gke-routing.b64 > /usr/local/bin/gke-routing-setup.sh && chmod 755 /usr/local/bin/gke-routing-setup.sh && rm /tmp/gke-routing.b64
  - sysctl -p /etc/sysctl.d/99-wireguard.conf
  - systemctl enable wg-quick@wg0
  - systemctl start wg-quick@wg0
  - sed -i 's/^[#]*DNSStubListener=.*/DNSStubListener=no/' /etc/systemd/resolved.conf
  - systemctl restart systemd-resolved
  - systemctl enable dnsmasq
  - systemctl start dnsmasq
  - /usr/local/bin/gke-routing-setup.sh
  - systemctl daemon-reload
  - systemctl enable gke-routing.service
