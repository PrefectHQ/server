import '@babel/polyfill'
import fetch from 'node-fetch'
import { print, GraphQLError } from 'graphql'
const HASURA_API_URL =
  process.env.HASURA_API_URL || 'http://localhost:3000/v1alpha1/graphql'

const PREFECT_API_URL =
  process.env.PREFECT_API_URL || 'http://localhost:4201/graphql/'

export const prefectExecutor = async ({ document, variables, context }) => {
  var headers = {}
  context = typeof context !== 'undefined' ? context : {}

  // populate x-prefect headers
  if (context.headers) {
    for (var key of Object.keys(context.headers)) {
      if (key.toLowerCase().startsWith('x-prefect')) {
        headers[key] = context.headers[key]
      }
    }
  }

  // parse GQL document
  const query = print(document)

  // issue remote query
  const fetchResult = await fetch(PREFECT_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers
    },
    body: JSON.stringify({ query, variables })
  })

  // get result
  const result = await fetchResult.json()

  // transform error keys into GraphQLErrors as a workaround for
  // https://github.com/ardatan/graphql-tools/pull/1572
  if (result.errors) {
    for (const error of result.errors) {
      Object.setPrototypeOf(error, GraphQLError.prototype)
    }
  }

  return result
}

export const hasuraExecutor = async ({ document, variables, context }) => {
  // parse GQL document
  const query = print(document)

  // issue remote query
  const fetchResult = await fetch(HASURA_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query, variables })
  })

  // get result
  const result = await fetchResult.json()

  // transform error keys into GraphQLErrors as a workaround for
  // https://github.com/ardatan/graphql-tools/pull/1572
  if (result.errors) {
    for (const error of result.errors) {
      Object.setPrototypeOf(error, GraphQLError.prototype)
    }
  }

  return result
}
