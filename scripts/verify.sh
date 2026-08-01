#!/usr/bin/env bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

fail() {
    echo -e "${RED}=========================${NC}"
    echo -e "${RED}❌ Verification Failed${NC}"
    echo -e "${RED}Fix the errors before pushing.${NC}"
    echo -e "${RED}=========================${NC}"
    exit 1
}

# Trap any error
trap 'fail' ERR

# Ensure we are in the root directory
cd "$(dirname "$0")/.."

echo -e "${CYAN}[1/11] Checking Node version...${NC}"
node --version
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[2/11] Checking Python version...${NC}"
python --version
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[3/11] Installing dependencies...${NC}"
pnpm install
python -m pip install -e ./apps/api[dev]
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[4/11] Ruff Linting...${NC}"
(cd apps/api && python -m ruff check .)
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[5/11] Ruff Formatting...${NC}"
(cd apps/api && python -m ruff format --check .)
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[6/11] MyPy Type Checking...${NC}"
(cd apps/api && python -m mypy src)
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[7/11] Pytest...${NC}"
(cd apps/api && python -m pytest)
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[8/11] Frontend Linting...${NC}"
pnpm lint
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[9/11] Frontend Type Checking...${NC}"
pnpm typecheck
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[10/11] Frontend Build...${NC}"
pnpm build
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${CYAN}[11/11] Backend Startup Validation...${NC}"
(cd apps/api && python -c "from src.main import app")
echo -e "${GREEN}✓ Passed\n${NC}"

echo -e "${GREEN}=========================${NC}"
echo -e "${GREEN}✅ Verification Passed${NC}"
echo -e "${GREEN}Ready to Commit & Push${NC}"
echo -e "${GREEN}=========================${NC}"
