#!/bin/bash
# Complete WireGuard VPN test script
# Tests connectivity from local machine through VPN to dev/stg/prd clusters

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${PROJECT_ID:-rhesis-dev-sandbox}"
REGION="${REGION:-europe-west4}"
PEER_ID="${PEER_ID:-admin-asad}"
CONFIG_PATH="${HOME}/wg0.conf"

echo "=========================================="
echo "WireGuard VPN Complete Test"
echo "=========================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Peer: $PEER_ID"
echo ""

# Step 1: Export client config
echo -e "${YELLOW}[1/8] Exporting client config...${NC}"
cd "$(dirname "$0")/.."
terraform output -json wireguard_peer_configs | jq -r ".\"${PEER_ID}\".config" > "$CONFIG_PATH"
chmod 600 "$CONFIG_PATH"
echo -e "${GREEN}✓ Config exported to $CONFIG_PATH${NC}"
echo ""

# Step 2: Start VPN tunnel
echo -e "${YELLOW}[2/8] Starting VPN tunnel...${NC}"
if sudo wg show | grep -q "interface:"; then
    echo "Tunnel already up, bringing down first..."
    sudo wg-quick down "$CONFIG_PATH" 2>/dev/null || true
fi
sudo wg-quick up "$CONFIG_PATH"
echo -e "${GREEN}✓ Tunnel started${NC}"
echo ""

# Step 3: Verify tunnel and handshake
echo -e "${YELLOW}[3/8] Verifying tunnel handshake...${NC}"
sleep 5
if sudo wg show | grep -q "latest handshake"; then
    echo -e "${GREEN}✓ Handshake established${NC}"
else
    echo -e "${RED}✗ No handshake - server not responding${NC}"
    exit 1
fi
echo ""

# Step 4: Ping WireGuard server
echo -e "${YELLOW}[4/8] Testing ping to WireGuard server (10.0.0.1)...${NC}"
if ping -c 2 -W 3 10.0.0.1 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ WireGuard server reachable${NC}"
else
    echo -e "${RED}✗ Cannot ping WireGuard server${NC}"
    exit 1
fi
echo ""

# Step 5: Ping dev VPC
echo -e "${YELLOW}[5/8] Testing ping to dev VPC (10.2.0.5)...${NC}"
if ping -c 2 -W 3 10.2.0.5 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Dev VPC reachable${NC}"
else
    echo -e "${RED}✗ Cannot ping dev VPC${NC}"
    exit 1
fi
echo ""

# Step 6: Ping stg VPC
echo -e "${YELLOW}[6/8] Testing ping to stg VPC (10.4.0.5)...${NC}"
if ping -c 2 -W 3 10.4.0.5 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Stg VPC reachable${NC}"
else
    echo -e "${RED}✗ Cannot ping stg VPC${NC}"
    exit 1
fi
echo ""

# Step 7: Ping prd VPC
echo -e "${YELLOW}[7/8] Testing ping to prd VPC (10.6.0.5)...${NC}"
if ping -c 2 -W 3 10.6.0.5 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Prd VPC reachable${NC}"
else
    echo -e "${RED}✗ Cannot ping prd VPC${NC}"
    exit 1
fi
echo ""

# Step 8: Test kubectl access to dev cluster
echo -e "${YELLOW}[8/8] Testing kubectl access to dev cluster...${NC}"
gcloud container clusters get-credentials gke-dev \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --internal-ip \
    --quiet

if kubectl get nodes --request-timeout=10s > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Kubectl access to dev cluster works${NC}"
    echo ""
    echo "Cluster nodes:"
    kubectl get nodes
else
    echo -e "${RED}✗ Cannot access dev cluster via kubectl${NC}"
    echo "Note: This might be due to GKE private endpoint enforcement."
    echo "Try without --internal-ip flag to use public endpoint."
fi
echo ""

echo "=========================================="
echo -e "${GREEN}All tests passed!${NC}"
echo "=========================================="
echo ""
echo "To stop the tunnel:"
echo "  sudo wg-quick down $CONFIG_PATH"
echo ""
