import { UUID } from 'crypto';

/** Valid environment types for projects */
export type ProjectEnvironment = 'development' | 'staging' | 'production';

/** Valid use cases for projects */
export type ProjectUseCase = 'chatbot' | 'assistant' | 'advisor' | 'other';

/** Valid sort orders for project queries */
export type SortOrder = 'asc' | 'desc';

/**
 * Base interface for common project properties
 * These are the core properties recognized by the backend API
 */
export interface ProjectBase {
  name: string;
  description?: string;
  is_active?: boolean;
  user_id?: UUID | string; // Allow string for mock data compatibility
  owner_id?: UUID | string; // Allow string for mock data compatibility
  organization_id?: UUID | string; // Allow string for mock data compatibility
}

/**
 * Interface for project query parameters
 * Used when fetching lists of projects
 */
export interface ProjectsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: SortOrder;
  $filter?: string | (string | null);
}

/**
 * Interface for project creation, extends base
 * This is what gets sent to the API when creating a project
 */
export interface ProjectCreate extends ProjectBase {
  icon?: string;
}

/**
 * Interface for project updates, all fields optional
 * Used when updating an existing project
 */
export type ProjectUpdate = Partial<ProjectBase>;

/**
 * User interface for nested objects in project responses
 */
export interface ProjectUser {
  id: UUID | string; // Allow string for mock data compatibility
  name: string;
  email: string;
  family_name: string;
  given_name: string;
  picture: string;
  organization_id: UUID | string; // Allow string for mock data compatibility
}

/**
 * Organization interface for nested objects in project responses
 */
export interface ProjectOrganization {
  id: UUID | string; // Allow string for mock data compatibility
  name: string;
  description: string;
  email: string;
  user_id: UUID | string; // Allow string for mock data compatibility
}

/**
 * System information for a project
 */
export interface ProjectSystem {
  name: string;
  description: string;
  primary_goals: string[];
  key_capabilities: string[];
}

/**
 * Agent definition for a project
 */
export interface ProjectAgent {
  name: string;
  description: string;
  responsibilities: string[];
}

/**
 * Generic project entity used for requirements, scenarios, and personas
 */
export interface ProjectEntity {
  name: string;
  description: string;
}

/**
 * Frontend-specific fields that aren't part of the backend model
 * These are used for UI purposes only
 */
export interface ProjectFrontendFields {
  environment?: ProjectEnvironment | string; // Allow string for mock data compatibility
  useCase?: ProjectUseCase | string; // Allow string for mock data compatibility
  icon?: string;
  tags?: string[];
  createdAt?: string; // For backward compatibility
  system?: ProjectSystem;
  agents?: ProjectAgent[];
  requirements?: ProjectEntity[];
  scenarios?: ProjectEntity[];
  personas?: ProjectEntity[];
}

/**
 * Full project model as returned by the API
 * Combines backend fields with nested objects and frontend-specific fields
 */
export interface Project extends ProjectBase, ProjectFrontendFields {
  id: UUID | string; // Allow string for mock data compatibility

  // Include standard timestamps if they exist in the API response
  created_at?: string;
  updated_at?: string;

  // Nested objects from API response
  user: ProjectUser;
  owner: ProjectUser;
  organization: ProjectOrganization;
}
