#!/bin/bash

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}📚 Installing docs dependencies...${NC}"
npm install

echo -e "${GREEN}🚀 Starting docs development server on port 3001...${NC}"
npm run dev
