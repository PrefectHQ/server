{{- define "towel.name" -}}
{{- default "towel" .Values.towel.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "towel.fullname" -}}
{{- printf "%s%s" (include "prefect-server.fullname" . ) "-towel" -}}
{{- end -}}

{{- define "towel.labels" -}}
{{ include "towel.selectorLabels" . }}
{{- include "prefect-server.otherLabels" . }}
{{- if .Values.towel.labels }}
{{ toYaml .Values.towel.labels }}
{{- end -}}
{{- end -}}

{{- define "towel.selectorLabels" -}}
{{ include "prefect-server.selectorLabels" . }}
app.kubernetes.io/name: {{ include "towel.name" . }}
{{- end -}}

{{- define "towel.annotations" -}}
{{- if .Values.global.annotations -}}
{{ .Values.global.annotations }}
{{ end -}}
{{- if .Values.towel.annotations -}}
{{ toYaml .Values.towel.annotations }}
{{- end -}}
{{- end -}}

