{{- define "ui.name" -}}
{{- default "ui" .Values.ui.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ui.fullname" -}}
{{- printf "%s%s" (include "prefect-server.fullname" . ) "-ui" -}}
{{- end -}}

{{- define "ui.labels" -}}
{{ include "ui.selectorLabels" . }}
{{- include "prefect-server.otherLabels" . }}
{{- if .Values.ui.labels }}
{{ toYaml .Values.ui.labels }}
{{- end -}}
{{- end -}}

{{- define "ui.selectorLabels" -}}
{{ include "prefect-server.selectorLabels" . }}
app.kubernetes.io/name: {{ include "ui.name" . }}
{{- end -}}

{{- define "ui.annotations" -}}
{{- if .Values.global.annotations -}}
{{ .Values.global.annotations }}
{{ end -}}
{{- if .Values.ui.annotations -}}
{{ toYaml .Values.ui.annotations }}
{{- end -}}
{{- end -}}

