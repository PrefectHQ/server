{{/*
  prefect-server.apollo-hostname:
    Determine the DNS name that the apollo service will be hosted at.
    K8s services are discoverable at: <service-name>-<namespace>
*/}}
{{- define "prefect-server.apollo-hostname" -}}
{{- $name := include "prefect-server.nameField" (merge (dict "component" "apollo") .) -}}
{{ printf "%s.%s" $name .Release.Namespace }}
{{- end -}}


{{/*
  prefect-server.apollo-api-url:
    Determine the url for the apollo api
*/}}
{{- define "prefect-server.apollo-api-url" -}}
{{- $host := include "prefect-server.apollo-hostname" . -}}
{{- $port := "4200" -}}
{{ printf "http://%s:%s/graphql/" $host $port }}
{{- end -}}

