FROM node:10.15.0
ARG VERSION
ENV PREFECT_SERVER_VERSION=${VERSION}

COPY . /apollo

RUN \
  cd /apollo \
  && npm ci && npm run build

WORKDIR /apollo
COPY post-start.sh .
RUN chmod +x post-start.sh

CMD ["npm", "run", "serve"]
