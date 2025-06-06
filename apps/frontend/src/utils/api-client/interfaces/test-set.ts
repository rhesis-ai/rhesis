import { UUID } from 'crypto';
import { Status } from './status';
import { Tag } from './tag';

export interface TestSetBase {
  name: string;
  description?: string;
  short_description?: string;
  slug?: string;
  status_id?: UUID;
  tags?: Tag[];
  attributes?: Record<string, any>;
  priority?: number;
  user_id?: UUID;
  owner_id?: UUID;
  assignee_id?: UUID;
  organization_id?: UUID;
}

// Organization interface for the nested organization data
export interface Organization {
  id: string;
  name: string;
  description?: string;
  email?: string;
  user_id?: string;
  tags?: Array<{
    id: string;
    name: string;
    icon_unicode?: string;
  }>;
}

// User interface for the nested user data
export interface User {
  id: string;
  name?: string;
  email?: string;
  family_name?: string;
  given_name?: string;
  picture?: string;
  organization_id?: string;
}

// LicenseType interface for the nested license_type data
export interface LicenseType {
  id: string;
  description?: string;
  type_name?: string;
  type_value?: string;
  user_id?: string;
  organization_id?: string;
}

export interface TestSet {
  id: UUID;
  name: string;
  description?: string;
  short_description?: string;
  slug?: string;
  status_id?: UUID;
  status: string | Status;
  status_details?: Status;
  tags?: Tag[];
  license_type_id?: UUID;
  license_type?: LicenseType;
  attributes?: {
    metadata?: {
      total_tests?: number;
      categories?: string[];
      behaviors?: string[];
      use_cases?: string[];
      topics?: string[];
      sample?: string;
      license_type?: string;
    };
    topics?: string[];
    behaviors?: string[];
    use_cases?: string[];
    categories?: string[];
  };
  user_id?: UUID;
  user?: User;
  owner_id?: UUID;
  owner?: User;
  assignee_id?: UUID;
  assignee?: User;
  priority?: number;
  organization_id?: UUID;
  organization?: Organization;
  is_published: boolean;
  visibility?: 'public' | 'organization' | 'user';
}

export interface TestSetCreate {
  name: string;
  description?: string;
  short_description?: string;
  slug?: string;
  status_id?: UUID;
  tags?: string[];
  attributes?: Record<string, any>;
  priority?: number;
}

export interface TestSetStatsHistorical {
  period: string;
  start_date: string;
  end_date: string;
  monthly_counts: Record<string, number>;
}

export interface StatsOptions {
  top?: number;
  months?: number;
  mode?: 'entity' | 'related_entity';
}

export interface TestSetStatsResponse {
  total: number;
  stats: {
    [dimension: string]: {
      dimension: string;
      total: number;
      breakdown: {
        [key: string]: number;
      };
    };
  };
  metadata: {
    generated_at: string;
    organization_id: string;
    entity_type: string;
  };
  history?: TestSetStatsHistorical;
}

export interface TestSetDetailStatsResponse {
  total: number;
  stats: {
    [dimension: string]: {
      dimension: string;
      total: number;
      breakdown: {
        [key: string]: number;
      };
    };
  };
  metadata: {
    generated_at: string;
    organization_id: string;
    entity_type: string;
    source_entity_type: string;
    source_entity_id: string;
  };
  history?: TestSetStatsHistorical;
}

// Test prompt creation model for bulk test set create
export interface TestPromptCreate {
  content: string;
  language_code?: string;
  demographic?: string;
  dimension?: string;
  expected_response?: string;
}

// Test data model for creating tests within a test set
export interface TestData {
  prompt: TestPromptCreate;
  behavior: string;
  category: string;
  topic: string;
  test_configuration?: Record<string, any>;
}

// Bulk test set creation request
export interface TestSetBulkCreate {
  name: string;
  description?: string;
  short_description?: string;
  tests: TestData[];
}

// Bulk test set creation response
export interface TestSetBulkResponse {
  id: UUID;
  name: string;
  description?: string;
  short_description?: string;
  status_id?: UUID;
  license_type_id?: UUID;
  user_id?: UUID;
  organization_id?: UUID;
  visibility?: string;
  attributes?: Record<string, any>;
}

// Test set association request
export interface TestSetBulkAssociateRequest {
  test_ids: UUID[];
}

// Test set association response
export interface TestSetBulkAssociateResponse {
  success: boolean;
  total_tests: number;
  message: string;
  metadata: {
    new_associations: number | null;
    existing_associations: number | null;
    invalid_associations: number | null;
    existing_test_ids: string[] | null;
    invalid_test_ids: string[] | null;
  };
}

export interface TestSetBulkDisassociateRequest {
  test_ids: UUID[];
}

export interface TestSetBulkDisassociateResponse {
  success: boolean;
  total_tests: number;
  removed_associations: number;
  message: string;
} 