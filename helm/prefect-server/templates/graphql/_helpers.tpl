
{{/*
  prefect-server.graphql-hostname:
    Determine the DNS name that the graphql service will be hosted at.
    K8s services are discoverable at: <service-name>-<namespace>
*/}}
{{- define "prefect-server.graphql-hostname" -}}
{{- $name := include "prefect-server.nameField" (merge (dict "component" "graphql") .) -}}
{{ printf "%s.%s" $name .Release.Namespace }}
{{- end -}}


{{/*
  prefect-server.graphql-api-url:
    Determine the url for the graphql api
*/}}
{{- define "prefect-server.graphql-api-url" -}}
{{- $host := include "prefect-server.graphql-hostname" . -}}
{{- $port := "4201" -}}
{{ printf "http://%s:%s/graphql/" $host $port }}
{{- end -}}


{{/*
  prefect-server.graphql-health-url:
    Determine the url for the graphql server health check
*/}}
{{- define "prefect-server.graphql-health-url" -}}
{{- $host := include "prefect-server.graphql-hostname" . -}}
{{- $port := "4201" -}}
{{ printf "http://%s:%s/health" $host $port }}
{{- end -}}
