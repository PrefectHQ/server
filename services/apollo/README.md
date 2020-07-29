# Apollo Server

This is our Apollo GraphQL service. It's responsible for stitching the other GraphQL schemas together and provides a single, public entrypoint to the Prefect API.

## Local Development

To start a local development server that restarts when files change:

```bash
npm install
npm run start
```

## Linting

This service uses eslint & prettier for code formatting & linting.

```bash
npm run lint
```

## Unit Testing

This service uses jest for unit testing.

```bash
npm run test
```
