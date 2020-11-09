{{/*
  Helper templates for prefect-server

  Includes:
    name
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


{{/*
  prefect-server.annotations:
    Provides the annotations for a component merging both global
    and local values
*/}}
{{- define "prefect-server.annotations" -}}
{{- $atns := .Values.annotations -}}
{{- $component_config := get .Values (include "prefect-server.componentName" .) -}}
{{/* Check if the component exists before getting annotations */}}
{{- if eq (typeOf $component_config | toString) "map[string]interface {}" -}}
  {{- $component_atns := $component_config.annotations -}}
  {{- if eq (typeOf $component_atns | toString) "map[string]interface {}" -}}
    {{- $atns = merge $component_atns $atns -}}
  {{- end -}}
{{- end -}}
{{- if $atns -}}
annotations:
  {{- $atns | toYaml | nindent 2 }}
{{ end -}}
{{- end -}}


{{- /*
  prefect-server.nameField:
    Populates a configuration name field's value by as {release}-{component}
    also allows prefix and suffix values to be passed
    NOTE: name fields are limited to 63 characters by the DNS naming spec
*/}}
{{- define "prefect-server.nameField" -}}
{{- $name := print (.namePrefix | default "") (include "prefect-server.componentName" .) (.nameSuffix | default "") -}}
{{ printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
  prefect-server.matchLabels:
    Provides K8s selection labels typically for use within the spec
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
    typically for use within the top-level metadata
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
    Provides the imagePullSecerts for a component merging global values
    from `.Values.imagePullSecrets` with `.Values.<component>.image.pullSecrets`
*/}}
{{- define "prefect-server.imagePullSecrets" -}}
{{- $pullSecrets := .Values.imagePullSecrets -}}

{{- $component_config := get .Values (include "prefect-server.componentName" .) -}}
{{/* Check if the component exists and concat secrets */}}
{{- if eq (typeOf $component_config | toString) "map[string]interface {}" -}}
  {{- $component_pullSecrets := $component_config.image.pullSecrets -}}
  {{- $pullSecrets = (concat $component_pullSecrets $pullSecrets) | uniq -}}
{{- end -}}

{{- /* Decide if something should be written */}}
{{- if ne ($pullSecrets | toJson) "[]" }}
imagePullSecrets: {{ $pullSecrets | toJson }}
{{ end -}}

{{- end }}


{{/*
  prefect-server.serviceAccountName: 
    Create the name of the service account to use
*/}}
{{- define "prefect-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{- $createName := include "prefect-server.nameField"  (merge (dict "componentName" "graphql") .) -}}
    {{- .Values.serviceAccount.name | default $createName -}}
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

  
{{/*
  env-unrap: 
    Converts a nested dictionary with keys `prefix` and `map`
    into a list of environment variable definitions, where each
    variable name is an uppercased concatenation of keys in the map
    starting with the original prefix and descending to each leaf.
    The variable value is then the quoted value of each leaf key.
*/}}
{{- define "env-unwrap" -}}
{{- $prefix := .prefix -}}
{{/* Iterate through all keys in the current map level */}}
{{- range $key, $val := .map -}}
{{- $key := upper $key -}}
{{/* Create an environment variable if this is a leaf */}}
{{- if ne (typeOf $val | toString) "map[string]interface {}" }}
- name: {{ printf "%s__%s" $prefix $key }}
  value: {{ $val | quote }}
{{/* Otherwise, recurse into each child key with an updated prefix */}}
{{- else -}}
{{- $prefix := (printf "%s__%s" $prefix $key) -}}
{{- $args := (dict "prefix" $prefix "map" $val)  -}}
{{- include "env-unwrap" $args -}}
{{- end -}}
{{- end -}}
{{- end -}}


{{/*
  prefect-server.envConfig:
    Define environment variables for prefect config.

    Includes a constant set of common variables as well as 
    generated environment variables from .Values.prefectConfig 
    using "env-unwrap"
*/}}
{{- define "prefect-server.envConfig" -}}
- name: PREFECT_SERVER__API__URL
  value: {{ include "prefect-server.hasura-api-url" . }}
- name: PREFECT_SERVER__DATABASE__HOST
  value: {{ include "prefect-server.postgres-hostname" . }}
- name: PREFECT_SERVER__DATABASE__PORT
  value: {{ .Values.postgresql.servicePort | quote }}
- name: PREFECT_SERVER__DATABASE__USERNAME
  value: {{ .Values.postgresql.postgresqlUsername }}
- name: PREFECT_SERVER__DATABASE__PASSWORD
  valueFrom:
    {{- include "prefect-server.postgres-secret-ref" . | nindent 4 }}
- name: PREFECT_SERVER__HASURA__HOST
  value: {{ include "prefect-server.hasura-hostname" . }}
- name: PREFECT_SERVER__HASURA__PORT
  value: {{ .Values.hasura.port | quote }}
- name: PREFECT_SERVER__SERVICES__APOLLO__PORT
  value: {{ .Values.apollo.port | quote }}
- name: PREFECT_SERVER__SERVICES__GRAPHQL__PORT
  value: {{ .Values.graphql.port | quote }}
{{- $args := (dict "prefix" "PREFECT_SERVER" "map" .Values.prefectConfig) -}}
{{- include "env-unwrap" $args -}}
{{- end }}

