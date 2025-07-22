#!/bin/bash

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Simple ASCII Art for RHESIS
echo -e "${CYAN}"
echo "  ____  _   _ _____ ____ ___ ____  "
echo " |  _ \| | | | ____/ ___|_ _/ ___| "
echo " | |_) | |_| |  _| \___ \| |\___ \ "
echo " |  _ <|  _  | |___ ___) | | ___) |"
echo " |_| \_\_| |_|_____|____/___|____/ "
echo -e "${NC}"

echo -e "${PURPLE}════════════════════════════════════════════════${NC}"
echo -e "${WHITE}🌐 Starting Rhesis Frontend Server${NC}"
echo -e "${PURPLE}════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}📦 Framework:${NC} ${GREEN}Next.js${NC}"
echo -e "${YELLOW}🔧 Command:${NC} ${GREEN}npm run dev --host${NC}"
echo -e "${YELLOW}🔄 Hot Reload:${NC} ${GREEN}enabled${NC}"
echo -e "${YELLOW}🎨 Development Mode:${NC} ${GREEN}active${NC}"
echo ""

echo -e "${BLUE}▶️  Launching frontend...${NC}"
echo ""

npm run dev --host 