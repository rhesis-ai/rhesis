{{/*
Expand the name of the chart.
*/}}
{{- define "rhesis.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "rhesis.fullname" -}}
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
{{- define "rhesis.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rhesis.labels" -}}
helm.sh/chart: {{ include "rhesis.chart" . }}
{{ include "rhesis.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rhesis.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rhesis.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "rhesis.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "rhesis.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the config map to use
*/}}
{{- define "rhesis.configMapName" -}}
{{- if .Values.secrets.configMaps.enabled }}
{{- .Values.secrets.configMaps.existingConfigMap }}
{{- else }}
{{- include "rhesis.fullname" . }}-config
{{- end }}
{{- end }}

{{/*
Create the name of the secret to use
*/}}
{{- define "rhesis.secretName" -}}
{{- if .Values.secrets.enabled }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "rhesis.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
Create the name of the postgres PVC to use
*/}}
{{- define "rhesis.postgresPVCName" -}}
{{- printf "%s-postgres-pvc" (include "rhesis.fullname" .) }}
{{- end }}

{{/*
Create the name of the redis PVC to use
*/}}
{{- define "rhesis.redisPVCName" -}}
{{- printf "%s-redis-pvc" (include "rhesis.fullname" .) }}
{{- end }}
