{{/*
  Helper templates for prefect-server

  Includes:
    name
    fullname
    componentName
    nameField
    matchLabels
    commonLabels
    imagePullSecrets
    serviceAccountName
    postgresql-hostname
    postgresql-connstr
    postgresql-secret-name
    postgresql-secret-ref
*/}}


{{/*
  prefect-server.name:
    Define a name for the application as {chart-name}
    NOTE: name fields are limited to 63 characters by the DNS naming spec
*/}}
{{- define "prefect-server.name" -}}
{{ .Values.nameOverride | default .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
  prefect-server.fullname:
    Create a fully qualified name as {release}-{chart-name}
    If release name contains chart name it will be used as a full name.
    NOTE: name fields are limited to 63 characters by the DNS naming spec
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


{{- /*
  prefect-server.componentName:
    Infers the name for a component. The component name is determined by:
    - 1: The provided scope's .componentName
    - 2: The template's filename if living in the root folder
    - 3: The template parent folder's name
*/}}
{{- define "prefect-server.componentName" -}}
{{- $file := .Template.Name | base | trimSuffix ".yaml" -}}
{{- $parent := .Template.Name | dir | base | trimPrefix "templates" -}}
{{- $component := .componentName | default $parent | default $file -}}
{{ $component }}
{{- end }}


{{- /*
  prefect-server.nameField:
    Populates the name field's value.
    NOTE: name fields are limited to 63 characters by the DNS naming spec
*/}}
{{- define "prefect-server.nameField" -}}
{{- $name := print (.namePrefix | default "") (include "prefect-server.componentName" .) (.nameSuffix | default "") -}}
{{ printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
  prefect-server.matchLabels:
    Provides K8s selection labels
*/}}
{{- define "prefect-server.matchLabels" -}}
{{- $composedName := printf "%s-%s" (include "prefect-server.name" .) (include "prefect-server.componentName" .) -}}
app.kubernetes.io/name: {{ .name | default $composedName }}
app.kubernetes.io/instance:  {{ .Release.Name }}
{{- if .Values.matchLabels }}
  {{- toYaml .Values.matchLabels }}
{{- end -}}
{{- end -}}


{{/*
  prefect-server.commonLabels:
    Provides common K8s labels, including "prefect-server.matchLabels"
*/}}
{{- define "prefect-server.commonLabels" -}}
{{ include "prefect-server.matchLabels" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ include "prefect-server.name" . }}
app.kubernetes.io/component: {{ include "prefect-server.componentName" . }}
{{- end -}}


{{- /*
  prefect-server.imagePullSecrets
    Augments passed .pullSecrets with $.Values.imagePullSecrets
*/}}
{{- define "prefect-server.imagePullSecrets" -}}
{{- /* Populate $_.list with all relevant entries */}}
{{- $_ := dict "list" (concat .image.pullSecrets .root.Values.imagePullSecrets | uniq) }}

{{- /* Decide if something should be written */}}
{{- if not (eq ($_.list | toJson) "[]") }}

{{- /* Process the $_.list where strings become dicts with a name key and the
strings become the name keys' values into $_.res */}}
{{- $_ := set $_ "res" list }}
{{- range $_.list }}
{{- if eq (typeOf .) "string" }}
{{- $__ := set $_ "res" (append $_.res (dict "name" .)) }}
{{- else }}
{{- $__ := set $_ "res" (append $_.res .) }}
{{- end }}
{{- end }}
{{- /* Write the results */}}
{{- $_.res | toJson }}
{{- end }}
{{- end }}


{{/*
  prefect-server.serviceAccountName: 
    Create the name of the service account to use
*/}}
{{- define "prefect-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{- .Values.serviceAccount.name | default (include "prefect-server.fullname" .) -}}
{{- else -}}
    {{- .Values.serviceAccount.name | default "default" -}}
{{- end -}}
{{- end -}}


{{/*
  prefect-server.postgres-hostname: 
    Generate the hostname of the postgresql service
    If a subchart is used, evaluate using its fullname function
      as {subchart.fullname}-{namespace}-{fqdnSuffix}
    Otherwise, the configured external hostname will be returned
*/}}
{{- define "prefect-server.postgres-hostname" -}}
{{- if .Values.postgresql.useSubChart -}}
  {{- $subchart_overrides := .Values.postgresql -}}
  {{- $name := include "postgresql.fullname" (dict "Values" $subchart_overrides "Chart" (dict "Name" "postgresql") "Release" .Release) -}}
  {{- printf "%s.%s.%s" $name .Release.Namespace .Values.fqdnSuffix -}}
{{- else -}}
  {{- .Values.postgresql.externalHostname -}}
{{- end -}}
{{- end -}}


{{/* 
  prefect-server.postgres-connstr:
    Generates the connection string for the postgresql service
    NOTE: Does not include password, which should be set via
      secret in PGPASSWORD on containers.
*/}}
{{- define "prefect-server.postgres-connstr" -}}
{{- $user := .Values.postgresql.postgresqlUsername -}}
{{- $host := include "prefect-server.postgres-hostname" . -}}
{{- $port := .Values.postgresql.servicePort | toString -}}
{{- $db := .Values.postgresql.postgresqlDatabase -}}
{{- printf "postgresql://%s@%s:%s/%s" $user $host $port $db -}}
{{- end -}}


{{/*
  prefect-server.postgres-secret-name:
    Get the name of the secret to be used for the postgresql
    user password. Generates {release-name}-postgresql if
    an existing secret is not set.
*/}}
{{- define "prefect-server.postgres-secret-name" -}}
{{- if .Values.postgresql.secretName -}}
  {{- .Values.postgresql.secretName -}}
{{- else -}}
  {{- printf "%s-%s" .Release.Name "postgresql" -}}
{{- end -}}
{{- end -}}

{{/*
  prefect-server.postgres-secret-ref:
    Generates a reference to the postgreqsql user password
    secret. 
*/}}
{{- define "prefect-server.postgres-secret-ref" -}}
secretKeyRef:
  name: {{ include "prefect-server.postgres-secret-name" . }}
  key: postgresql-password
{{- end -}}
