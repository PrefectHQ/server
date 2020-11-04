{{- define "apollo.name" -}}
{{- default "apollo" .Values.apollo.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "apollo.fullname" -}}
{{- printf "%s%s" (include "prefect-server.fullname" . ) "-apollo" -}}
{{- end -}}

{{- define "apollo.fqdn" -}}
{{- $name := include "apollo.fullname" . -}}
{{- $ns := include "global.namespace" . }}
{{- $suffix := .Values.global.fqdnSuffix }}
{{- printf "%s.%s.%s" $name $ns $suffix -}}
{{- end -}}

{{- define "apollo.api-url" -}}
{{- if .Values.apollo.ingress.enabled -}}
    {{/*
    Since the UI needs to point at a locally accessible version of the
    Apollo API (the browser is making requests) we use the first fqdn
    path rather than the in-cluster path
    */}}
    {{- $ingress := (index .Values.apollo.ingress.hosts 0) -}}
    {{- $host := $ingress.host -}}
    {{- $path := (index $ingress.paths 0) -}}
    {{- printf "http://%s%s" $host $path -}}
{{- else -}}
    {{- $host := include "apollo.fqdn" . -}}
    {{- $port := .Values.global.apollo.port | toString -}}
    {{- printf "http://%s:%s/graphql" $host $port -}}
{{- end -}}
{{- end -}}

{{- define "apollo.labels" -}}
{{ include "apollo.selectorLabels" . }}
{{- include "prefect-server.otherLabels" . }}
{{- if .Values.apollo.labels }}
{{ toYaml .Values.apollo.labels }}
{{- end -}}
{{- end -}}

{{- define "apollo.selectorLabels" -}}
{{ include "prefect-server.selectorLabels" . }}
app.kubernetes.io/name: {{ include "apollo.name" . }}
{{- end -}}

{{- define "apollo.annotations" -}}
{{- if .Values.global.annotations -}}
{{ .Values.global.annotations }}
{{ end -}}
{{- if .Values.apollo.annotations -}}
{{ toYaml .Values.apollo.annotations }}
{{- end -}}
{{- end -}}

