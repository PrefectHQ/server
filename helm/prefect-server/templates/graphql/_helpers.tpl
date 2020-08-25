{{- define "graphql.name" -}}
{{- default "graphql" .Values.graphql.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "graphql.fullname" -}}
{{- printf "%s%s" (include "prefect-server.fullname" . ) "-graphql" -}}
{{- end -}}

{{- define "graphql.fqdn" -}}
{{- $name := include "graphql.fullname" . -}}
{{- $ns := include "global.namespace" . }}
{{- $suffix := .Values.global.fqdnSuffix }}
{{- printf "%s.%s.%s" $name $ns $suffix -}}
{{- end -}}

{{- define "graphql.api-url" -}}
{{- $host := include "graphql.fqdn" . -}}
{{- $port := .Values.global.graphql.port | toString -}}
{{ printf "http://%s:%s/graphql/" $host $port }}
{{- end -}}

{{- define "graphql.health-url" -}}
{{- $host := include "graphql.fqdn" . -}}
{{- $port := .Values.global.graphql.port | toString -}}
{{ printf "http://%s:%s/health" $host $port }}
{{- end -}}


{{- define "graphql.labels" -}}
{{ include "graphql.selectorLabels" . }}
{{- include "prefect-server.otherLabels" . }}
{{- if .Values.graphql.labels }}
{{ toYaml .Values.graphql.labels }}
{{- end -}}
{{- end -}}

{{- define "graphql.selectorLabels" -}}
{{ include "prefect-server.selectorLabels" . }}
app.kubernetes.io/name: {{ include "graphql.name" . }}
{{- end -}}

{{- define "graphql.annotations" -}}
{{- if .Values.global.annotations -}}
{{ .Values.global.annotations }}
{{ end -}}
{{- if .Values.graphql.annotations -}}
{{ toYaml .Values.graphql.annotations }}
{{- end -}}
{{- end -}}

