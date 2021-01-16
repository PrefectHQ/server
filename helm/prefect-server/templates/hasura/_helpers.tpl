
{{/*
  prefect-server.hasura-hostname:
    Determine the DNS name that the hasura service will be hosted at.
    K8s services are discoverable at: <service-name>-<namespace>
*/}}
{{- define "prefect-server.hasura-hostname" -}}
{{- $name := include "prefect-server.nameField" (merge (dict "component" "hasura") .) -}}
{{ printf "%s.%s" $name .Release.Namespace }}
{{- end -}}


{{/*
  prefect-server.hasura-api-url:
    Determine the path that the hasura api will be available at
*/}}
{{- define "prefect-server.hasura-api-url" -}}
{{- $port := .Values.hasura.service.port | toString -}}
{{ printf "http://%s:%s/v1alpha1/graphql" (include "prefect-server.hasura-hostname" .) $port }}
{{- end -}}
