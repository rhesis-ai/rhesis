{{/*
Expand the name of the chart.
*/}}
{{- define "rhesis.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
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
Create chart label value.
*/}}
{{- define "rhesis.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "rhesis.labels" -}}
helm.sh/chart: {{ include "rhesis.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/*
Resolve the PostgreSQL hostname.
When postgresql subchart is enabled, use its service name.
Otherwise fall back to externalDatabase.host.
*/}}
{{- define "rhesis.postgresql.host" -}}
{{- if .Values.postgresql.enabled -}}
{{- printf "%s-postgresql" .Release.Name -}}
{{- else -}}
{{- required "externalDatabase.host is required when postgresql.enabled=false" .Values.externalDatabase.host -}}
{{- end -}}
{{- end }}

{{/*
Resolve the Valkey (Redis-compatible) hostname.
When valkey subchart is enabled, use its master service name.
Otherwise fall back to externalValkey.host.
*/}}
{{- define "rhesis.valkey.host" -}}
{{- if .Values.valkey.enabled -}}
{{- printf "%s-valkey-primary" .Release.Name -}}
{{- else -}}
{{- required "externalValkey.host is required when valkey.enabled=false" .Values.externalValkey.host -}}
{{- end -}}
{{- end }}

{{/*
Build a full image reference.
Usage: include "rhesis.image" (dict "imageValues" .Values.backend "global" .Values.global)
*/}}
{{- define "rhesis.image" -}}
{{- $registry := .global.registry -}}
{{- $repository := .imageValues.image.repository -}}
{{- $tag := coalesce .imageValues.image.tag .global.imageTag "latest" -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Pod security context block. Accepts a component values dict via "component" key
to support per-component disableSecurityContext flag.
Usage: include "rhesis.podSecurityContext" (dict "Values" .Values "component" .Values.backend)
*/}}
{{- define "rhesis.podSecurityContext" -}}
{{- if and .Values.podSecurityContext.enabled (not .component.disableSecurityContext) }}
securityContext:
  fsGroup: {{ .Values.podSecurityContext.fsGroup }}
  runAsUser: {{ .Values.podSecurityContext.runAsUser }}
  runAsGroup: {{ .Values.podSecurityContext.runAsGroup }}
  {{- if .Values.podSecurityContext.fsGroupChangePolicy }}
  fsGroupChangePolicy: {{ .Values.podSecurityContext.fsGroupChangePolicy }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
Container security context block.
Usage: include "rhesis.containerSecurityContext" (dict "Values" .Values "component" .Values.backend)
*/}}
{{- define "rhesis.containerSecurityContext" -}}
{{- if and .Values.containerSecurityContext.enabled (not .component.disableSecurityContext) }}
securityContext:
  allowPrivilegeEscalation: {{ .Values.containerSecurityContext.allowPrivilegeEscalation }}
  readOnlyRootFilesystem: {{ .Values.containerSecurityContext.readOnlyRootFilesystem }}
  runAsNonRoot: {{ .Values.containerSecurityContext.runAsNonRoot }}
  runAsUser: {{ .Values.containerSecurityContext.runAsUser }}
  runAsGroup: {{ .Values.containerSecurityContext.runAsGroup }}
  {{- if .Values.containerSecurityContext.capabilities }}
  capabilities:
    {{- toYaml .Values.containerSecurityContext.capabilities | nindent 4 }}
  {{- end }}
{{- end }}
{{- end }}
