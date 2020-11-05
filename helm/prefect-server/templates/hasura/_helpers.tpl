{{- define "prefect-server.hasura-hostname" -}}
{{/* 
    The componentName has to be hardcoded here so other components
    that need this url do not insert their name instead
*/}}
{{- $name := (include "prefect-server.nameField" (merge (dict "componentName" "hasura") .)) -}}
{{ printf "%s.%s.%s" $name .Release.Namespace .Values.fqdnSuffix }}
{{- end -}}

{{- define "prefect-server.hasura-api-url" -}}
{{- $port := .Values.hasura.port | toString -}}
{{ printf "http://%s:%s/v1alpha1/graphql" (include "prefect-server.hasura-hostname" .) $port }}
{{- end -}}
