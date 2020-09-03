FROM node:12-slim

ARG VERSION
ENV PREFECT_SERVER_VERSION=${VERSION}

WORKDIR /apollo
COPY . .

RUN npm install && \
    npm run build && \
    chmod +x post-start.sh

CMD ["npm", "run", "serve"]
