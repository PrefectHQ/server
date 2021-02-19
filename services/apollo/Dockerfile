ARG NODE_VERSION=${NODE_VERSION:-14.15.1}
FROM node:${NODE_VERSION}-slim

# Prefect Version, default to MASTER
ARG PREFECT_VERSION
ENV PREFECT_VERSION=${PREFECT_VERSION:-master}

# Prefect Server Version, default to MASTER
ARG PREFECT_SERVER_VERSION
ENV PREFECT_SERVER_VERSION=${PREFECT_SERVER_VERSION:-master}

ARG RELEASE_TIMESTAMP
ENV RELEASE_TIMESTAMP=$RELEASE_TIMESTAMP

# Architecture to support. Necessary for a working tini entrypoint on non-x86/64 builds
ARG ARCH
ENV ARCH=${ARCH:-amd64}

# Image Labels
LABEL maintainer="help@prefect.io"
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="apollo"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_VERSION}
LABEL org.label-schema.build-date=${RELEASE_TIMESTAMP}

RUN apt-get update \
 && apt-get install curl --no-install-recommends -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install tini with checksum verification
# Once we upgrade to a newer version of Debian (Buster+), we can just `apt-get install tini`
ENV TINI_VERSION v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-${ARCH} /tini-${ARCH}
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-${ARCH}.sha256sum /tini.sha256sum
RUN echo "$(cat tini.sha256sum)" | sha256sum -c && mv /tini-${ARCH} /tini
RUN chmod +x /tini

WORKDIR /apollo
COPY . .

RUN npm ci && \
    npm run build && \
    chmod +x post-start.sh

ENTRYPOINT ["/tini", "-g", "--"]
CMD ["npm", "run", "serve"]
