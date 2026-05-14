import { BaseApiClient } from './base-client';
import {
  ExperimentCreate,
  ExperimentDetail,
  ExperimentRead,
  ExperimentUpdate,
  ExperimentVersion,
  ExperimentVersionCreate,
  LabelBindRequest,
  ParameterSchema,
  ProjectLabels,
  ResolveResponse,
  ExperimentResultsRunItem,
  ExperimentResultsVersionItem,
} from './interfaces/parameters';

/**
 * Client for project-scoped parameter management endpoints.
 *
 * Phases 1 & 2 surface: schema GET/PUT, experiment header CRUD with
 * an inline-versions sub-resource, project-labels bind/unbind, and
 * the canonical resolver. Phases 4+ extend this client with run
 * snapshotting hooks; nothing in those phases reshapes the existing
 * methods.
 */
export class ParametersClient extends BaseApiClient {
  // ----------------------------------------------------------------- //
  // Schema                                                            //
  // ----------------------------------------------------------------- //

  async getSchema(projectId: string): Promise<ParameterSchema> {
    return this.fetch<ParameterSchema>(
      `/projects/${projectId}/parameters/schema`
    );
  }

  async putSchema(
    projectId: string,
    schema: ParameterSchema
  ): Promise<ParameterSchema> {
    return this.fetch<ParameterSchema>(
      `/projects/${projectId}/parameters/schema`,
      {
        method: 'PUT',
        body: JSON.stringify(schema),
      }
    );
  }

  // ----------------------------------------------------------------- //
  // Project labels                                                    //
  // ----------------------------------------------------------------- //

  async getLabels(projectId: string): Promise<ProjectLabels> {
    return this.fetch<ProjectLabels>(
      `/projects/${projectId}/parameters/labels`
    );
  }

  async putLabel(
    projectId: string,
    labelName: string,
    payload: LabelBindRequest
  ): Promise<ProjectLabels> {
    return this.fetch<ProjectLabels>(
      `/projects/${projectId}/parameters/labels/${encodeURIComponent(labelName)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      }
    );
  }

  async deleteLabel(
    projectId: string,
    labelName: string
  ): Promise<ProjectLabels> {
    return this.fetch<ProjectLabels>(
      `/projects/${projectId}/parameters/labels/${encodeURIComponent(labelName)}`,
      { method: 'DELETE' }
    );
  }

  // ----------------------------------------------------------------- //
  // Resolver                                                          //
  // ----------------------------------------------------------------- //

  async resolve(
    projectId: string,
    args: { label?: string; experimentId?: string; version?: string } = {}
  ): Promise<ResolveResponse> {
    const params = new URLSearchParams();
    if (args.label) params.set('label', args.label);
    if (args.experimentId) params.set('experiment_id', args.experimentId);
    if (args.version) params.set('version', args.version);
    const qs = params.toString();
    return this.fetch<ResolveResponse>(
      `/projects/${projectId}/parameters/resolve${qs ? `?${qs}` : ''}`
    );
  }

  // ----------------------------------------------------------------- //
  // Experiments — list / create are project-scoped                    //
  // ----------------------------------------------------------------- //

  async listProjectExperiments(
    projectId: string,
    args: { skip?: number; limit?: number } = {}
  ): Promise<ExperimentRead[]> {
    const params = new URLSearchParams();
    if (args.skip !== undefined) params.set('skip', String(args.skip));
    if (args.limit !== undefined) params.set('limit', String(args.limit));
    const qs = params.toString();
    return this.fetch<ExperimentRead[]>(
      `/projects/${projectId}/experiments${qs ? `?${qs}` : ''}`
    );
  }

  async createProjectExperiment(
    projectId: string,
    payload: ExperimentCreate
  ): Promise<ExperimentRead> {
    return this.fetch<ExperimentRead>(`/projects/${projectId}/experiments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // ----------------------------------------------------------------- //
  // Experiments — singleton CRUD + versions sub-resource              //
  // ----------------------------------------------------------------- //

  async getExperiment(experimentId: string): Promise<ExperimentDetail> {
    return this.fetch<ExperimentDetail>(`/experiments/${experimentId}`);
  }

  async patchExperiment(
    experimentId: string,
    payload: ExperimentUpdate
  ): Promise<ExperimentDetail> {
    return this.fetch<ExperimentDetail>(`/experiments/${experimentId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteExperiment(experimentId: string): Promise<ExperimentRead> {
    return this.fetch<ExperimentRead>(`/experiments/${experimentId}`, {
      method: 'DELETE',
    });
  }

  async listExperimentVersions(
    experimentId: string
  ): Promise<ExperimentVersion[]> {
    return this.fetch<ExperimentVersion[]>(
      `/experiments/${experimentId}/versions`
    );
  }

  async getExperimentVersion(
    experimentId: string,
    version: string
  ): Promise<ExperimentVersion> {
    return this.fetch<ExperimentVersion>(
      `/experiments/${experimentId}/versions/${encodeURIComponent(version)}`
    );
  }

  async createExperimentVersion(
    experimentId: string,
    payload: ExperimentVersionCreate
  ): Promise<ExperimentVersion> {
    return this.fetch<ExperimentVersion>(
      `/experiments/${experimentId}/versions`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  async getExperimentResultsByRun(
    experimentId: string,
    limit: number = 100
  ): Promise<{ items: ExperimentResultsRunItem[] }> {
    return this.fetch<{ items: ExperimentResultsRunItem[] }>(
      `/experiments/${experimentId}/results?group_by=run&limit=${limit}`
    );
  }

  async getExperimentResultsByVersion(
    experimentId: string,
    limit: number = 100
  ): Promise<{ items: ExperimentResultsVersionItem[] }> {
    return this.fetch<{ items: ExperimentResultsVersionItem[] }>(
      `/experiments/${experimentId}/results?group_by=version&limit=${limit}`
    );
  }
}
