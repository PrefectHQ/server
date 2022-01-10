#!/bin/bash
set -eu

while true; do
    echo "[APOLLO] Waiting GraphQL service at $PREFECT_API_HEALTH_URL to be active"
    curl -s $PREFECT_API_HEALTH_URL | grep -i "ok" \
        && echo "[APOLLO] GraphQL service is up and healthy" && break
    sleep 5
done

echo "[APOLLO] Starting PM2"
echo "{\"apps\": [{\"name\": \"apollo-server\", \"script\": \"./dist/index.js\", \"exec_mode\": \"cluster\", \"instances\": ${APOLLO_PM2_INSTANCES:-0}}]}" > process.json
npx pm2-runtime start process.json