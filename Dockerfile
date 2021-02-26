# syntax=docker/dockerfile:1.0.0-experimental

ARG PYTHON_VERSION=${PYTHON_VERSION:-3.7}
FROM python:${PYTHON_VERSION}-slim-buster

# Prefect Version, default to MASTER
ARG PREFECT_SERVER_VERSION
ENV PREFECT_SERVER_VERSION=${PREFECT_SERVER_VERSION:-master}

ARG PREFECT_VERSION
ENV PREFECT_VERSION=${PREFECT_VERSION:-master}

ARG RELEASE_TIMESTAMP
ENV RELEASE_TIMESTAMP=$RELEASE_TIMESTAMP

# Set system locale
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

# Image Labels
LABEL maintainer="help@prefect.io"
LABEL io.prefect.python-version=${PYTHON_VERSION}
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="prefect_server"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_SERVER_VERSION}
LABEL org.label-schema.build-date=${RELEASE_TIMESTAMP}

RUN apt update && \
    apt install -y gcc git curl tini && \
    mkdir /root/.prefect/ && \
    pip install --no-cache-dir git+https://github.com/PrefectHQ/prefect.git@${PREFECT_VERSION} && \
    apt remove -y git && \
    apt clean && apt autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY . /prefect-server

RUN \
    cd /prefect-server \
    && pip install -e .

WORKDIR /prefect-server

ENTRYPOINT ["tini", "-g", "--"]
CMD python
