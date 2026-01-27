#!/usr/bin/env bash
set -euo pipefail

(cd web && npm install)
(cd web && npm run build)

mkdir -p server/public
cp -R web/dist/* server/public/

go build -o tavily-proxy ./server
echo "Built: tavily-proxy"

