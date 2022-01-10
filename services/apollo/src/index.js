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
const APOLLO_API_BODY_LIMIT = process.env.APOLLO_API_BODY_LIMIT || '5mb'
const APOLLO_API_ENABLE_PLAYGROUND =
  process.env.APOLLO_API_ENABLE_PLAYGROUND == 'false' ? false : true

const APOLLO_API_LOGGING =
  process.env.APOLLO_API_LOGGING == 'false' ? false : true
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

function logInfo(...items) {
  // "console.log is synchronous" - https://stackoverflow.com/a/6856325
  if (APOLLO_API_LOGGING == true) console.log(...items)
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
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
    logInfo(`Error fetching GQL health: ${err}`)
    return false
  }
  const data = await response.json()
  if (data.version === PREFECT_SERVER_VERSION) {
    return true
  }

  logInfo(
    `Mismatched PREFECT_SERVER_VERSION: apollo=${PREFECT_SERVER_VERSION} graphql=${data.version}`
  )
  return false
}

async function buildSchema() {
  logInfo('Building schema...')

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

  logInfo('Building schema complete!')
  return schema
}

async function runServer() {
  const server = new PrefectApolloServer({
    schema: await buildSchema(),
    debug: false,
    introspection: true,
    playground: APOLLO_API_ENABLE_PLAYGROUND,
    tracing: false, // set to true to see performance metrics w/ every request
    // this function is called whenever a request is made to the server in order to populate
    // the graphql context
    context: ({ req, connection }) => {
      if (req) {
        return { headers: req.headers }
      }
    }
  })
  server.applyMiddleware({
    app,
    path: '/',
    bodyParserConfig: { limit: APOLLO_API_BODY_LIMIT }
  })
  const listener = app.listen({
    host: APOLLO_API_BIND_ADDRESS,
    port: APOLLO_API_PORT,
    family: 'IPv4'
  })
  if ('APOLLO_KEEPALIVE_TIMEOUT' in process.env) {
    listener.keepAliveTimeout = process.env.APOLLO_KEEPALIVE_TIMEOUT * 1000
    listener.headersTimeout = (process.env.APOLLO_KEEPALIVE_TIMEOUT + 5) * 1000
  }
  console.log(
    `Server ready at http://${APOLLO_API_BIND_ADDRESS}:${APOLLO_API_PORT} 🚀 (version: ${PREFECT_SERVER_VERSION})`
  )
}

async function send_telemetry_event(event) {
  try {
    // TODO add timeout
    const body = JSON.stringify({
      source: 'prefect_server',
      type: event,
      payload: {
        id: TELEMETRY_ID,
        prefect_server_version: PREFECT_SERVER_VERSION,
        api_version: '0.2.0'
      }
    })
    logInfo(`Sending telemetry to Prefect Technologies, Inc.: ${body}`)

    fetch('https://sens-o-matic.prefect.io/', {
      method: 'post',
      body,
      headers: {
        'Content-Type': 'application/json',
        'X-Prefect-Event': 'prefect_server-0.2.0'
      }
    })
  } catch (error) {
    logInfo(`Error sending telemetry event: ${error.message}`)
  }
}

async function runServerForever() {
  if (TELEMETRY_ENABLED) {
    send_telemetry_event('startup')
    setInterval(() => {
      send_telemetry_event('heartbeat')
    }, 600000) // send heartbeat every 10 minutes
  }

  try {
    await runServer()
  } catch (e) {
    logInfo(e, 'Trying again in 3 seconds...')
    await sleep(3000)
    await runServerForever()
  } 
}

runServerForever()