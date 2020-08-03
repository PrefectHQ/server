# syntax=docker/dockerfile:1.0.0-experimental

FROM python:3.7
ARG VERSION
ENV PREFECT_SERVER_VERSION=${VERSION}

ARG PREFECT_VERSION=master
ENV PREFECT_VERSION=$PREFECT_VERSION

RUN pip install git+https://github.com/PrefectHQ/prefect.git@${PREFECT_VERSION}

COPY . /prefect-server

RUN \
    cd /prefect-server \
    && pip install -e .

WORKDIR /prefect-server
CMD python
