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
{{- $port := (.Values.apollo.service.port | default 4200) -}}
{{ printf "http://%s:%v/graphql" $host $port }}
{{- end -}}

