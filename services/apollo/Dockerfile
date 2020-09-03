ARG NODE_VERSION=${NODE_VERSION:12}
FROM node::${NODE_VERSION}-slim

# Prefect Version, default to MASTER
ARG PREFECT_SERVER_VERSION
ENV PREFECT_SERVER_VERSION=${PREFECT_SERVER_VERSION:-master}

ARG RELEASE_TIMESTAMP
ENV RELEASE_TIMESTAMP=$RELEASE_TIMESTAMP

# Image Labels
LABEL maintainer="help@prefect.io"
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="apollo"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_SERVER_VERSION}
LABEL org.label-schema.build-date=${RELEASE_TIMESTAMP}

WORKDIR /apollo
COPY . .

RUN npm install && \
    npm run build && \
    chmod +x post-start.sh

CMD ["npm", "run", "serve"]
