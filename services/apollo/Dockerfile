# Nodejs version, default to 14
ARG NODE_VERSION=${NODE_VERSION:-14}
# Prefect Version, default to MASTER
ARG PREFECT_VERSION
# Prefect Server Version, default to MASTER
ARG PREFECT_SERVER_VERSION
# Prefect Apollo Release timestamp
ARG RELEASE_TIMESTAMP

FROM node:${NODE_VERSION}-buster-slim

ENV PREFECT_VERSION=${PREFECT_VERSION:-master}
ENV PREFECT_SERVER_VERSION=${PREFECT_SERVER_VERSION:-master}
ENV RELEASE_TIMESTAMP=$RELEASE_TIMESTAMP
ENV NODE_ENV=production

# Image Labels
LABEL maintainer="help@prefect.io"
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="apollo"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_VERSION}
LABEL org.label-schema.build-date=${RELEASE_TIMESTAMP}

WORKDIR /apollo

RUN apt update \
 && apt install curl tini --no-install-recommends -y \
 && apt clean \
 && rm -rf /var/lib/apt/lists/*

# To allow caching during local development
COPY package-lock.json .
COPY package.json .
RUN npm ci

COPY . .
RUN npm run build
RUN chmod +x post-start.sh

ENTRYPOINT ["tini", "--"]
CMD ["./post-start.sh"]