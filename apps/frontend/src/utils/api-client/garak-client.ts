import { BaseApiClient } from './base-client';

/**
 * Garak probe module information
 */
export interface GarakProbeModule {
  name: string;
  description: string;
  probe_count: number;
  total_prompt_count: number;
  tags: string[];
  default_detector: string | null;
  rhesis_category: string;
  rhesis_topic: string;
  rhesis_behavior: string;
}

/**
 * List probes response
 */
export interface GarakProbesListResponse {
  garak_version: string;
  modules: GarakProbeModule[];
  total_modules: number;
}

/**
 * Probe detail response
 */
export interface GarakProbeDetailResponse {
  name: string;
  description: string;
  probe_classes: string[];
  probe_count: number;
  total_prompt_count: number;
  tags: string[];
  default_detector: string | null;
  rhesis_mapping: {
    category: string;
    topic: string;
    behavior: string;
  };
  probes: Array<{
    class_name: string;
    full_name: string;
    description: string;
    tags: string[];
    prompt_count: number;
    detector: string | null;
  }>;
}

/**
 * Import request
 */
export interface GarakImportRequest {
  modules: string[];
  test_set_name: string;
  description?: string;
}

/**
 * Import preview response
 */
export interface GarakImportPreviewResponse {
  garak_version: string;
  total_probes: number;
  total_prompts: number;
  total_tests: number;
  detector_count: number;
  detectors: string[];
  modules: Array<{
    name: string;
    probe_count: number;
    prompt_count: number;
    category: string;
    topic: string;
    behavior: string;
  }>;
}

/**
 * Import response
 */
export interface GarakImportResponse {
  test_set_id: string;
  test_set_name: string;
  test_count: number;
  metric_count: number;
  garak_version: string;
  modules: string[];
}

/**
 * Sync preview response
 */
export interface GarakSyncPreviewResponse {
  can_sync: boolean;
  old_version: string;
  new_version: string;
  to_add: number;
  to_remove: number;
  unchanged: number;
  modules: string[];
  last_synced_at: string | null;
}

/**
 * Sync response
 */
export interface GarakSyncResponse {
  added: number;
  removed: number;
  unchanged: number;
  new_garak_version: string;
  old_garak_version: string;
}

/**
 * Client for Garak integration API endpoints
 */
export class GarakClient extends BaseApiClient {
  /**
   * List all available Garak probe modules
   */
  async listProbeModules(): Promise<GarakProbesListResponse> {
    return this.fetch<GarakProbesListResponse>('/garak/probes');
  }

  /**
   * Get detailed information about a specific probe module
   */
  async getProbeModuleDetail(
    moduleName: string
  ): Promise<GarakProbeDetailResponse> {
    return this.fetch<GarakProbeDetailResponse>(`/garak/probes/${moduleName}`);
  }

  /**
   * Preview what will be imported
   */
  async previewImport(
    request: GarakImportRequest
  ): Promise<GarakImportPreviewResponse> {
    return this.fetch<GarakImportPreviewResponse>('/garak/import/preview', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Import selected Garak probe modules as a test set
   */
  async importProbes(
    request: GarakImportRequest
  ): Promise<GarakImportResponse> {
    return this.fetch<GarakImportResponse>('/garak/import', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Preview sync changes for a Garak-imported test set
   */
  async previewSync(testSetId: string): Promise<GarakSyncPreviewResponse> {
    return this.fetch<GarakSyncPreviewResponse>(
      `/garak/sync/${testSetId}/preview`
    );
  }

  /**
   * Sync a Garak-imported test set with latest probes
   */
  async syncTestSet(testSetId: string): Promise<GarakSyncResponse> {
    return this.fetch<GarakSyncResponse>(`/garak/sync/${testSetId}`, {
      method: 'POST',
    });
  }
}
