#!/bin/sh
# Run from a clean checkout on the dedicated AWS Lightsail server.
# runtime.env (0600) is supplied privately; never commit it or put secrets in user-data.
set -eu
: "${EW_PUBLIC_HOST:?Set the public HTTPS hostname}"
: "${EW_IMAGE:=embodiweave:$(git rev-parse --short=12 HEAD)}"
: "${EW_ENV_FILE:=/opt/embodiweave/runtime.env}"
[ -f "$EW_ENV_FILE" ] || { echo "Missing private runtime.env" >&2; exit 1; }
docker network inspect embodiweave-net >/dev/null 2>&1 || docker network create embodiweave-net >/dev/null
docker volume create embodiweave-data >/dev/null
docker volume create embodiweave-caddy-data >/dev/null
docker volume create embodiweave-caddy-config >/dev/null
# The dedicated deployment script replaces only this project's two containers.
for name in ew-proxy ew-api; do
  if docker container inspect "$name" >/dev/null 2>&1; then docker rm -f "$name" >/dev/null; fi
done
docker run -d --name ew-api --restart unless-stopped --network embodiweave-net \
  --memory 1500m --memory-swap 2g --cpus 1.8 --pids-limit 256 \
  --log-opt max-size=10m --log-opt max-file=3 \
  --env-file "$EW_ENV_FILE" -e EW_ARTIFACTS=/data -e EW_PERSISTENT_ARTIFACTS=1 \
  -e EW_DEPLOYED_POLICY="${EW_DEPLOYED_POLICY:-robust-20261016140226-352fd7}" \
  -e EW_LATEST_VALIDATION_POLICY="${EW_LATEST_VALIDATION_POLICY:-robust-20261016140226-352fd7}" \
  -e EW_GIT_COMMIT="$(git rev-parse HEAD)" -v embodiweave-data:/data "$EW_IMAGE"
docker run -d --name ew-proxy --restart unless-stopped --network embodiweave-net \
  --log-opt max-size=10m --log-opt max-file=3 -p 80:80 -p 443:443 \
  -e EW_PUBLIC_HOST="$EW_PUBLIC_HOST" -v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v embodiweave-caddy-data:/data -v embodiweave-caddy-config:/config caddy:2@sha256:685ae3d7c34d9b5f8caeddc5d14051db7bbd88ff1f5a2fa0c16bd8ca328fb7af
