#!/bin/bash
set -eu
curl -s $GRAPHQL_SERVICE_HOST:$GRAPHQL_SERVICE_PORT/health | grep $PREFECT_SERVER_VERSION && echo "Service Healthy" || kill 1