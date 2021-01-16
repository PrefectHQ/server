#!/bin/bash
set -eu

while true; do
    echo "Checking GraphQL service at $PREFECT_API_HEALTH_URL ..."
    curl -s $PREFECT_API_HEALTH_URL | grep "ok" \
        && echo "GraphQL service healthy!" && break
    sleep 1
done
