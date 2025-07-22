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
echo -e "${WHITE}🚀 Starting Rhesis Backend Server${NC}"
echo -e "${PURPLE}════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}📍 Host:${NC} ${GREEN}0.0.0.0${NC}"
echo -e "${YELLOW}🔌 Port:${NC} ${GREEN}8080${NC}"
echo -e "${YELLOW}📝 Log Level:${NC} ${GREEN}debug${NC}"
echo -e "${YELLOW}🔄 Auto-reload:${NC} ${GREEN}enabled${NC}"
echo ""

echo -e "${BLUE}▶️  Launching server...${NC}"
echo ""

uvicorn rhesis.backend.app.main:app --host 0.0.0.0 --port 8080 --log-level debug --reload 