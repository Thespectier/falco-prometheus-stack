#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-hanabi_}"
OUT="${OUT:-hanabi-images-$(date +%Y%m%d-%H%M%S).tar}"
COMPRESS="${COMPRESS:-1}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found" >&2
  exit 1
fi

images="$(
  docker image ls --format '{{.Repository}}:{{.Tag}}' \
    | grep -E "^${PREFIX}" \
    | grep -vE '^<none>:' \
    | sort -u
)"

if [[ -z "${images}" ]]; then
  echo "no images matched prefix: ${PREFIX}" >&2
  exit 1
fi

echo "exporting images:"
echo "${images}" | sed 's/^/  - /'

docker save -o "${OUT}" ${images}

if [[ "${COMPRESS}" == "1" ]]; then
  gzip -f -1 "${OUT}"
  echo "done: ${OUT}.gz"
else
  echo "done: ${OUT}"
fi
