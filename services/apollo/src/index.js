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
const APOLLO_API_ENABLE_PLAYGROUND = process.env.APOLLO_API_ENABLE_PLAYGROUND == 'false' ? false : true

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


/*
  Creates a single capture group for the entirety of an IPv4 address (including trailing . :)

  Example:
    https://35.237.156.161:8200/v1/auth/jwt/login

  Captures:
    35.237.156.161:

  Adapted from https://stackoverflow.com/a/36760050/13419215
*/
const ipv4Regex = /((25[0-5]|(2[0-4]|1[0-9]|[1-9]|)[0-9])(\.|\:|\b(?!$)|$)){4}/g

/*
  Creates a single capture group for the entirety of an IPv6 address

  Example:
    http://2001:db8:85a3:8d3:1319:8a2e:370:7348/

  Captures:
    2001:db8:85a3:8d3:1319:8a2e:370:7348

  From https://stackoverflow.com/a/17871737/13419215
*/
const ipv6Regex = /(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))/g


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
    playground: APOLLO_API_ENABLE_PLAYGROUND,
    tracing: false, // set to true to see performance metrics w/ every request
    formatError: error => {
      // When passed here, errors have 4 fields: message, locations, path, and extensions
      // 1. Message is the human-readable explanation of what's gone wrong
      // 2. Locations is field that's meant to explain where things went wrong
      // we're stripping locations because it's at best inaccurate and at worst exposing
      // info we don't want users to see.
      // 3. Path is the route that was called e.g., `create_project`
      // 4. Extensions is where we put anything additional we'd like to include. By default,
      // it always includes a code, which is the GQL equivalent of a response code describing
      // what's gone wrong
      log(JSON.stringify(error))
      const errorJson = {
        path: error.path,
        message: error.message,
        extensions: error.extensions
      }

      // handle the case in which the operation takes longer than 3s
      if (error.message.includes('database query error')) {
        errorJson.message = 'Operation timed out'
        errorJson.extensions = { code: 'API_ERROR' }
      }
      // handle intentionally obfuscated API errors
      else if (error.message.includes('An internal API error occurred')) {
        errorJson.extensions = { code: 'API_ERROR' }
      }
      // handle the case in which we have intra-cluster connectivity issues (generally at deploy-time)
      // the way refused connections surface changes depending on whether the error was raised through Python
      else if (
        error.message.includes('ECONNREFUSED') ||
        error.message.includes('Connection refused') ||
        error.message.includes('connection error') ||
        error.message.includes('ENOTFOUND') ||
        error.message.includes('postgres') ||
        error.message.includes('EAI_AGAIN') ||
        error.message.includes('EHOSTUNREACH') ||
        error.message.includes('ECONNRESET')
      ) {
        errorJson.message = 'Unable to complete operation'
        errorJson.extensions = { code: 'API_ERROR' }
      } // handle version locking errors so the Core client doesn't have to rely on a fragile string match
      else {
        errorJson.message = error.message.replace(
          ipv4Regex,
          // Replaces all IPv4 elements with • but maintains : in the last position
          // if it exists
          match => '•••.•••.•••.•••' + (match.substr(-1) === ':' ? ':' : '')
        )

        errorJson.message = error.message.replace(
          ipv6Regex,
          // Replaces all IPv6 elements with a fake • sequence
          '••••:••••:••••:••••::::'
        )
      }

      return errorJson
    },
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
        payload: {
          id: TELEMETRY_ID,
          prefect_server_version: PREFECT_SERVER_VERSION,
          api_version: '0.2.0'
        }
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
