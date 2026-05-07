#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${1:-${MCP_ENV_FILE:-.env.deploy}}"

cd "${REPO_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

read_env_var() {
  local key="$1"
  local line

  line="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    return 1
  fi

  printf '%s\n' "${line#*=}"
}

if [[ -z "${MCP_IMAGE+x}" ]]; then
  MCP_IMAGE="$(read_env_var MCP_IMAGE || true)"
fi

if [[ -z "${MCP_BUILD_LOCAL+x}" ]]; then
  MCP_BUILD_LOCAL="$(read_env_var MCP_BUILD_LOCAL || true)"
fi

if [[ -z "${MCP_SKIP_PULL+x}" ]]; then
  MCP_SKIP_PULL="$(read_env_var MCP_SKIP_PULL || true)"
fi

export MCP_ENV_FILE="${ENV_FILE}"
export MCP_IMAGE
export MCP_BUILD_LOCAL
export MCP_SKIP_PULL

docker compose --env-file "${ENV_FILE}" -f compose.yaml config >/dev/null

if [[ "${MCP_BUILD_LOCAL:-0}" == "1" ]]; then
  IMAGE_TAG="${MCP_IMAGE:-knowledge-base-mcp:local}"
  docker build -t "${IMAGE_TAG}" .
elif [[ "${MCP_SKIP_PULL:-0}" != "1" ]]; then
  docker compose --env-file "${ENV_FILE}" -f compose.yaml pull
fi

docker compose --env-file "${ENV_FILE}" -f compose.yaml up -d --remove-orphans
docker compose --env-file "${ENV_FILE}" -f compose.yaml ps
