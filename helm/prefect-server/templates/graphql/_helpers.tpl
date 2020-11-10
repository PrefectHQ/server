{{- define "prefect-server.graphql-hostname" -}}
{{/* 
    The componentName has to be hardcoded here so other components
    that need this url do not insert their name instead
*/}}
{{- $name := (include "prefect-server.nameField" (merge (dict "componentName" "graphql") .)) -}}
{{ printf "%s.%s.%s" $name .Release.Namespace .Values.fqdnSuffix }}
{{- end -}}

{{- define "prefect-server.graphql-api-url" -}}
{{- $host := include "prefect-server.graphql-hostname" . -}}
{{- $port := "4201" -}}
{{ printf "http://%s:%s/graphql/" $host $port }}
{{- end -}}

{{- define "prefect-server.graphql-health-url" -}}
{{- $host := include "prefect-server.graphql-hostname" . -}}
{{- $port := "4201" -}}
{{ printf "http://%s:%s/health" $host $port }}
{{- end -}}
