import { BaseApiClient } from './base-client';
import {
  EnvironmentBindRequest,
  EnvironmentRegisterRequest,
  ExperimentCreate,
  ExperimentDetail,
  ExperimentRead,
  ExperimentUpdate,
  ExperimentVersion,
  ExperimentVersionCreate,
  ParameterSchema,
  ProjectEnvironments,
  ResolveResponse,
  ExperimentResultsRunItem,
  ExperimentResultsVersionItem,
} from './interfaces/parameters';

/**
 * Client for project-scoped parameter management endpoints.
 *
 * Phases 1 & 2 surface: schema GET/PUT, experiment header CRUD with
 * an inline-versions sub-resource, project-environments bind/unbind, and
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
  // Project environments                                              //
  // ----------------------------------------------------------------- //

  async getEnvironments(projectId: string): Promise<ProjectEnvironments> {
    return this.fetch<ProjectEnvironments>(
      `/projects/${projectId}/parameters/environments`
    );
  }

  async registerEnvironment(
    projectId: string,
    payload: EnvironmentRegisterRequest
  ): Promise<ProjectEnvironments> {
    return this.fetch<ProjectEnvironments>(
      `/projects/${projectId}/parameters/environments`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  async putEnvironment(
    projectId: string,
    environmentName: string,
    payload: EnvironmentBindRequest
  ): Promise<ProjectEnvironments> {
    return this.fetch<ProjectEnvironments>(
      `/projects/${projectId}/parameters/environments/${encodeURIComponent(environmentName)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      }
    );
  }

  async deleteEnvironment(
    projectId: string,
    environmentName: string
  ): Promise<ProjectEnvironments> {
    return this.fetch<ProjectEnvironments>(
      `/projects/${projectId}/parameters/environments/${encodeURIComponent(environmentName)}`,
      { method: 'DELETE' }
    );
  }

  // ----------------------------------------------------------------- //
  // Resolver                                                          //
  // ----------------------------------------------------------------- //

  async resolve(
    projectId: string,
    args: { environment?: string; experimentId?: string; version?: string } = {}
  ): Promise<ResolveResponse> {
    const params = new URLSearchParams();
    if (args.environment) params.set('environment', args.environment);
    if (args.experimentId) params.set('experiment_id', args.experimentId);
    if (args.version) params.set('version', args.version);
    const qs = params.toString();
    return this.fetch<ResolveResponse>(
      `/projects/${projectId}/parameters/resolve${qs ? `?${qs}` : ''}`
    );
  }

  // ----------------------------------------------------------------- //
  // Experiments — cross-project list with OData filter                //
  // ----------------------------------------------------------------- //

  async listExperiments(
    args: {
      skip?: number;
      limit?: number;
      sort_by?: string;
      sort_order?: 'asc' | 'desc';
      filter?: string;
    } = {}
  ): Promise<{ data: ExperimentRead[]; totalCount: number }> {
    const resp = await this.fetchPaginated<ExperimentRead>('/experiments', {
      skip: args.skip ?? 0,
      limit: args.limit ?? 50,
      sort_by: args.sort_by,
      sort_order: args.sort_order,
      $filter: args.filter,
    });
    return { data: resp.data, totalCount: resp.pagination.totalCount };
  }

  // ----------------------------------------------------------------- //
  // Experiments — per-project list / create                           //
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

  async deleteExperiment(
    experimentId: string,
    options?: { cascadeEnvironments?: boolean }
  ): Promise<ExperimentRead> {
    const query = options?.cascadeEnvironments
      ? '?cascade_environments=true'
      : '';
    return this.fetch<ExperimentRead>(`/experiments/${experimentId}${query}`, {
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
