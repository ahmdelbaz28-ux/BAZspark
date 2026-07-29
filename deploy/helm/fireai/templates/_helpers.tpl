{{/*
Expand the name of the chart.
*/}}
{{- define "fireai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "fireai.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "fireai.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "fireai.labels" -}}
helm.sh/chart: {{ include "fireai.chart" . }}
{{ include "fireai.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fireai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fireai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "fireai.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "fireai.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Redis fullname
*/}}
{{- define "fireai.redis.fullname" -}}
{{- printf "%s-redis" (include "fireai.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Redis labels
*/}}
{{- define "fireai.redis.labels" -}}
{{ include "fireai.labels" . }}
app.kubernetes.io/component: redis
{{- end }}

{{/*
PostgreSQL fullname
*/}}
{{- define "fireai.postgresql.fullname" -}}
{{- printf "%s-postgresql" (include "fireai.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
PostgreSQL labels
*/}}
{{- define "fireai.postgresql.labels" -}}
{{ include "fireai.labels" . }}
app.kubernetes.io/component: postgresql
{{- end }}

{{/*
Secret name
*/}}
{{- define "fireai.secret.name" -}}
{{- printf "%s-secrets" (include "fireai.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}