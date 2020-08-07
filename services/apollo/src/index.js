import '@babel/polyfill'
import fetch from 'node-fetch'
import { ApolloServer } from 'apollo-server-express'
import { prefectExecutor, hasuraExecutor } from './executors'
import { introspectSchema, wrapSchema } from '@graphql-tools/wrap'
import { stitchSchemas } from '@graphql-tools/stitch'
import { v4 as uuidv4 } from 'uuid'

const express = require('express')
const APOLLO_API_PORT = process.env.APOLLO_API_PORT || '4200'
const APOLLO_API_BIND_ADDRESS = process.env.APOLLO_API_BIND_ADDRESS || '0.0.0.0'

const PREFECT_API_HEALTH_URL =
  process.env.PREFECT_API_HEALTH_URL || 'http://localhost:4201/health'
const PREFECT_SERVER_VERSION = process.env.PREFECT_SERVER_VERSION || 'UNKNOWN'

const TELEMETRY_ENABLED_RAW =
  process.env.PREFECT_SERVER__TELEMETRY__ENABLED || 'false'
// Convert from a TOML boolean to a JavaScript boolean
const TELEMETRY_ENABLED = TELEMETRY_ENABLED_RAW == 'true' ? true : false
const TELEMETRY_ID = uuidv4()
// --------------------------------------------------------------------
// Server
const app = express()
const depthLimit = require('graphql-depth-limit')
class PrefectApolloServer extends ApolloServer {
  async createGraphQLServerOptions(req, res) {
    const options = await super.createGraphQLServerOptions(req, res)
    return {
      ...options,
      validationRules: [depthLimit(7)]
    }
  }
}

function log(...items) {
  console.log(...items)
}

async function buildSchema() {
  log('Building schema...')

  // create remote Hasura schema
  const hasuraSchema = wrapSchema({
    schema: await introspectSchema(hasuraExecutor),
    executor: hasuraExecutor
  })

  // create remote Prefect schema
  const prefectSchema = wrapSchema({
    schema: await introspectSchema(prefectExecutor),
    executor: prefectExecutor
  })

  // stitch schemas
  const schema = stitchSchemas({
    subschemas: [{ schema: hasuraSchema }, { schema: prefectSchema }]
  })

  log('Building schema complete!')
  return schema
}

// check the graphql server to see if version matches the expected version from our environment
async function checkUpstreamVersion() {
  if (PREFECT_SERVER_VERSION == 'UNKNOWN') {
    return false
  }

  var response = null
  try {
    response = await fetch(PREFECT_API_HEALTH_URL)
  } catch (err) {
    log(`Error fetching GQL health: ${err}`)
    return false
  }
  const data = await response.json()
  if (data.version === PREFECT_SERVER_VERSION) {
    return true
  }

  log(
    `Mismatched PREFECT_SERVER_VERSION: apollo=${PREFECT_SERVER_VERSION} graphql=${data.version}`
  )
  return false
}

async function runServer() {
  const server = new PrefectApolloServer({
    schema: await buildSchema(),
    debug: false,
    introspection: true,
    playground: true,
    tracing: true,
    // this function is called whenever a request is made to the server in order to populate
    // the graphql context
    context: ({ req, connection }) => {
      if (req) {
        return { headers: req.headers }
      }
    }
  })
  server.applyMiddleware({ app, path: '/', bodyParserConfig: { limit: '1mb' } })
  app.listen({
    host: APOLLO_API_BIND_ADDRESS,
    port: APOLLO_API_PORT,
    family: 'IPv4'
  })
  console.log(
    `Server ready at http://${APOLLO_API_BIND_ADDRESS}:${APOLLO_API_PORT} 🚀 (version: ${PREFECT_SERVER_VERSION})`
  )
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function send_telemetry_event(event) {
  if (TELEMETRY_ENABLED) {
    try {
      // TODO add timeout
      const body = JSON.stringify({
        source: 'prefect_server',
        type: event,
        payload: { id: TELEMETRY_ID, prefect_server_version: PREFECT_SERVER_VERSION }
      })
      log(`Sending telemetry to Prefect Technologies, Inc.: ${body}`)

      fetch('https://sens-o-matic.prefect.io/', {
        method: 'post',
        body,
        headers: {
          'Content-Type': 'application/json',
          'X-Prefect-Event': 'prefect_server-0.2.0'
        }
      })
    } catch (error) {
      log(`Error sending telemetry event: ${error.message}`)
    }
  }
}

async function runServerForever() {
  try {
    await runServer()
    send_telemetry_event('startup')
    if (TELEMETRY_ENABLED) {
      setInterval(() => {
        send_telemetry_event('heartbeat')
      }, 600000) // send heartbeat every 10 minutes
    }
  } catch (e) {
    log(e)
    log('Trying again in 3 seconds...')
    await sleep(3000)
    await runServerForever()
  }
}

runServerForever()
