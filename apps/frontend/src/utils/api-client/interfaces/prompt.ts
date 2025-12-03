import { UUID } from 'crypto';

export interface Tag {
  id: UUID;
  name: string;
  icon_unicode?: string;
  organization_id?: UUID;
}

// Base prompt interface
export interface PromptBase {
  content: string;
  demographic_id?: UUID;
  category_id?: UUID;
  attack_category_id?: UUID;
  topic_id?: UUID;
  language_code: string;
  behavior_id?: UUID;
  parent_id?: UUID;
  prompt_template_id?: UUID;
  expected_response?: string;
  source_id?: UUID;
  user_id?: UUID;
  organization_id?: UUID;
  status_id?: UUID;
  tags?: Tag[];
}

// Create and update interfaces
export type PromptCreate = PromptBase;

export type PromptUpdate = Partial<PromptBase>;

// Full prompt entity with id and timestamps
export interface Prompt extends PromptBase {
  id: UUID;
  nano_id?: string;
  created_at: string;
  updated_at: string;
  counts?: {
    comments: number;
    tasks: number;
  };
}
