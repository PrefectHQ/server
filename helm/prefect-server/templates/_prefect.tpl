{{/*
   * Helpers for prefect configuration.
   */}}
{{/*
unwrap writes env toml overrides for dict

Converts a nested dictionary with keys:
`prefix` and `map`, into a list of environment
variable definitions, where each key is concat
of uppercased keys starting with original prefix
and the values are quoted leaf values.
*/}}
{{- define "env-unwrap" -}}
{{- $prefix := .prefix -}}
{{- range $key, $val := .map -}}
{{- $key := upper $key -}}
{{- if ne (typeOf $val | toString) "map[string]interface {}" }}
- name: {{ printf "%s__%s" $prefix $key }}
  value: {{ $val | quote }}
{{- else -}}
{{- $prefix := (printf "%s__%s" $prefix $key) -}}
{{- $args := (dict "prefix" $prefix "map" $val)  -}}
{{- include "env-unwrap" $args -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{/*
Define environment variables for prefect config.

We define environment variables for all specified
values in "prefect.config" plus some specific
ones based on other settings (ports, hosts).
*/}}
{{- define "prefect.env-config" -}}
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

