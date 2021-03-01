ARG NODE_VERSION=${NODE_VERSION:-14.15.1}
FROM node:${NODE_VERSION}-buster-slim

# Prefect Version, default to MASTER
ARG PREFECT_VERSION
ENV PREFECT_VERSION=${PREFECT_VERSION:-master}

# Prefect Server Version, default to MASTER
ARG PREFECT_SERVER_VERSION
ENV PREFECT_SERVER_VERSION=${PREFECT_SERVER_VERSION:-master}

ARG RELEASE_TIMESTAMP
ENV RELEASE_TIMESTAMP=$RELEASE_TIMESTAMP

# Image Labels
LABEL maintainer="help@prefect.io"
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="apollo"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_VERSION}
LABEL org.label-schema.build-date=${RELEASE_TIMESTAMP}

RUN apt-get update \
 && apt-get install curl tini --no-install-recommends -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /apollo
COPY . .

RUN npm ci && \
    npm run build && \
    chmod +x post-start.sh

ENTRYPOINT ["tini", "-g", "--"]
CMD ["npm", "run", "serve"]
