#!/bin/bash
set -eu

while true; do
    curl -s $GRAPHQL_SERVICE_HOST:$GRAPHQL_SERVICE_PORT/health | grep "ok" \
        && echo "GraphQL service healthy!" && break
    sleep 1
done