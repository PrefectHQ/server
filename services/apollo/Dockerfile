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

# Image Labels
LABEL maintainer="help@prefect.io"
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="apollo"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_VERSION}
LABEL org.label-schema.build-date=${RELEASE_TIMESTAMP}

RUN apt-get update \
 && apt-get install curl gpg dirmngr --no-install-recommends -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install TINI per
# - https://github.com/krallin/tini#signed-binaries
# - https://github.com/f-secure-foundry/usbarmory-debian-base_image/issues/9
# Once we upgrade to a newer version of Debian (Buster+), we can just `apt-get install tini` and remove gpg/dirmngr
ENV TINI_VERSION v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini.asc /tini.asc
RUN mkdir -p ~/.gnupg && echo "disable-ipv6" >> ~/.gnupg/dirmngr.conf \
 && gpg --batch --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 595E85A6B1B4779EA4DAAEC70B588DFF0527A9B7 \
 && gpg --batch --verify /tini.asc /tini
RUN chmod +x /tini

WORKDIR /apollo
COPY . .

RUN npm ci && \
    npm run build && \
    chmod +x post-start.sh

#ENTRYPOINT ["/tini", "-g", "--"]
CMD ["npm", "run", "serve"]
