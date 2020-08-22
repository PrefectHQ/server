{{- define "hasura.name" -}}
{{- default "hasura" .Values.hasura.nameOverride | trunc 63 | trimSuffix "-" -}}
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

