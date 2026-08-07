import { UUID } from 'crypto';

// Base prompt interface
export interface PromptBase {
  content: string;
  language_code: string;
  expected_response?: string;
}

// Create and update interfaces
export type PromptCreate = PromptBase;

export type PromptUpdate = Partial<PromptBase>;

// Full prompt entity with id and timestamps
export interface Prompt extends PromptBase {
  id: UUID;
}
