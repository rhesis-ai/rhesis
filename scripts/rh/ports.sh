#!/bin/bash
# Every port ./rh dev uses. Quick start has its own, in .env.docker.
#
#   RHESIS_PORT_OFFSET=100 ./rh dev up   shifts the whole stack
#   DEV_FLOWER_PORT=5556 ./rh dev worker shifts one port
#
# Ports reach the env files at ./rh dev init time — re-run it after a change.

RHESIS_PORT_OFFSET="${RHESIS_PORT_OFFSET:-0}"

# Distinct from prod (5432/6379) and test (10001/10002).
DEV_POSTGRES_PORT="${DEV_POSTGRES_PORT:-$((11000 + RHESIS_PORT_OFFSET))}"
DEV_REDIS_PORT="${DEV_REDIS_PORT:-$((11001 + RHESIS_PORT_OFFSET))}"

DEV_BACKEND_PORT="${DEV_BACKEND_PORT:-$((8080 + RHESIS_PORT_OFFSET))}"
DEV_FRONTEND_PORT="${DEV_FRONTEND_PORT:-$((3000 + RHESIS_PORT_OFFSET))}"
DEV_FLOWER_PORT="${DEV_FLOWER_PORT:-$((5555 + RHESIS_PORT_OFFSET))}"
DEV_CHATBOT_PORT="${DEV_CHATBOT_PORT:-$((8000 + RHESIS_PORT_OFFSET))}"
DEV_POLYPHEMUS_PORT="${DEV_POLYPHEMUS_PORT:-$((8082 + RHESIS_PORT_OFFSET))}"

# The worker binds nothing in dev — only Flower listens. The mock servers set
# their own ports in apps/developer-tools/mock_*/main.py (18080, 18090).
