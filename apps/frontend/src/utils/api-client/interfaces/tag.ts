import { UUID } from 'crypto';

export enum EntityType {
  TEST = 'Test',
  TEST_SET = 'TestSet',
  TEST_RUN = 'TestRun',
  TEST_RESULT = 'TestResult',
  PROMPT = 'Prompt',
  PROMPT_TEMPLATE = 'PromptTemplate',
  BEHAVIOR = 'Behavior',
  CATEGORY = 'Category',
  ENDPOINT = 'Endpoint',
  USE_CASE = 'UseCase',
  RESPONSE_PATTERN = 'ResponsePattern',
  PROJECT = 'Project',
  ORGANIZATION = 'Organization',
  METRIC = 'Metric',
  MODEL = 'Model',
  SOURCE = 'Source',
}

export interface TagBase {
  name: string;
  icon_unicode?: string;
  organization_id?: UUID;
  user_id?: UUID;
}

export type TagCreate = TagBase;

export type TagUpdate = Partial<TagBase>;

export interface Tag extends TagBase {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export interface TagAssignment {
  entity_id: UUID;
  entity_type: EntityType;
}
