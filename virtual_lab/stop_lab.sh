#!/bin/bash
# ==============================================================================
# PentexOne Virtual Lab — Stop Script
# ==============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}▶ Stopping PentexOne Virtual Lab...${NC}"

cd wifi_lab
docker compose down

echo -e "${GREEN}✓ Lab stopped${NC}"
