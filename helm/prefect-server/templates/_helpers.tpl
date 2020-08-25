{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "prefect-server.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "prefect-server.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "prefect-server.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "prefect-server.otherLabels" }}
{{- if .Values.global.labels }}
{{ toYaml .Values.global.labels }}
{{- end -}}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "prefect-server.labels" -}}
helm.sh/chart: {{ include "prefect-server.chart" . }}
{{ include "prefect-server.selectorLabels" . }}
{{- include "prefect-server.otherLabels" . }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "prefect-server.selectorLabels" -}}
app.kubernetes.io/part-of: {{ include "prefect-server.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Values.global.selectorLabels }}
{{ toYaml .Values.global.selectorLabels }}
{{- end -}}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "prefect-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "prefect-server.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{/*
Postgresql FQDN.

Uses subchart "postgreql.fullname" evaluated with subchart values.

Thanks to https://stackoverflow.com/a/61816134/435563, and
https://stackoverflow.com/a/49604964/435563

TODO: following is not working ... for the moment, hard-coded
  {{- $name := include "postgresql.fullname" (set (deepCopy .) "Values" .Values.postgresql) -}}

*/}}
{{- define "postgresql.fqdn" -}}
{{- if .Values.postgresqlEnabled -}}
  {{- $name := "prefect-server-postgresql" -}}
  {{- $ns := include "global.namespace" . }}
  {{- $suffix := .Values.global.fqdnSuffix }}
  {{- printf "%s.%s.%s" $name $ns $suffix -}}
{{- else -}}
  {{- .Values.postgresqlExternalHost -}}
{{- end -}}
{{- end -}}


{{/* 
Postgresl db connect url.

Does not include password, which should be set via
secret in PGPASSWORD on containers.
*/}}
{{- define "postgresql-url" -}}
{{- $user := .Values.global.postgresql.postgresqlUsername -}}
{{- $host := include "postgresql.fqdn" . -}}
{{- $port := .Values.global.postgresql.servicePort | toString -}}
{{- $db := .Values.global.postgresql.postgresqlDatabase -}}
{{- printf "postgresql://%s@%s:%s/%s" $user $host $port $db -}}
{{- end -}}
{{/*
Namespace: for the moment, just release namespace.
*/}}
{{- define "global.namespace" -}}
{{- .Release.Namespace -}}
{{- end -}}

{{/*
Name for default postgres secret (if not existing).
*/}}
{{- define "postgresql.default-secret-name" -}}
{{ printf "%s%s" .Release.Name "-postgresql" }}
{{- end -}}

{{/*
Secret key reference for postgres database password
*/}}
{{- define "postgresql.password-secret-ref" -}}
{{- $secret := dict "name" "" "key" "postgresql-password" -}}
{{- if .Values.global.postgresql.existingSecret -}}
  {{- $_ := set $secret "name" .Values.global.postgresql.existingSecret -}}
{{- else if .Values.postgresql.existingSecret -}}
  {{- $_ := set $secret "name" .Values.postgresql.existingSecret -}}
{{- else -}}
  {{- $secret_name := include "postgresql.default-secret-name" . -}}
  {{- $_ := set $secret "name" $secret_name -}}
{{- end -}}
secretKeyRef:
  name: {{ get $secret "name" }}
  key: {{ get $secret "key" }}
{{- end -}}
