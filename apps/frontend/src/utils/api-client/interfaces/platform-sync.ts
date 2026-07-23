/**
 * Types for the local-only platform sync feature.
 * Mirrors `apps/backend/src/rhesis/backend/app/schemas/platform_sync.py`.
 */

export interface PlatformSyncResource {
  key: string;
  label: string;
  dependencies: string[];
  description?: string | null;
}

export interface SyncGap {
  resource: string;
  name: string;
  field: string;
  reason: string;
}

export interface ResourceSyncResult {
  resource: string;
  label: string;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  gaps: SyncGap[];
  errors: string[];
}

export interface PlatformSyncSummary {
  base_url: string;
  source_organization_id?: string | null;
  source_user_email?: string | null;
  results: ResourceSyncResult[];
  gaps: SyncGap[];
}

export interface PlatformSyncRequest {
  api_key: string;
  base_url?: string;
  resources: string[];
}
