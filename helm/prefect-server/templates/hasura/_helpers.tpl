{{- define "hasura.name" -}}
{{- default "hasura" .Values.hasura.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "hasura.fullname" -}}
{{- printf "%s%s" (include "prefect-server.fullname" . ) "-hasura" -}}
{{- end -}}

{{- define "hasura.fqdn" -}}
{{- $name := include "hasura.fullname" . -}}
{{- $ns := include "global.namespace" . }}
{{- $suffix := .Values.global.fqdnSuffix }}
{{- printf "%s%s%s" $name $ns $suffix -}}
{{- end -}}

{{- define "hasura.api-url" -}}
{{- $host := include "hasura.fqdn" . -}}
{{- $port := .Values.global.hasura.port -}}
{{ printf "http://%s:%s/v1alpha/graphql" $host $port }}
{{- end -}}

{{- define "hasura.labels" -}}
{{ include "hasura.selectorLabels" . }}
{{- include "prefect-server.otherLabels" . }}
{{- if .Values.hasura.labels }}
{{ toYaml .Values.hasura.labels }}
{{- end -}}
{{- end -}}

{{- define "hasura.selectorLabels" -}}
{{ include "prefect-server.selectorLabels" . }}
app.kubernetes.io/name: {{ include "hasura.name" . }}
{{- end -}}

{{- define "hasura.annotations" -}}
{{- if .Values.global.annotations -}}
{{ .Values.global.annotations }}
{{ end -}}
{{- if .Values.hasura.annotations -}}
{{ toYaml .Values.hasura.annotations }}
{{- end -}}
{{- end -}}

