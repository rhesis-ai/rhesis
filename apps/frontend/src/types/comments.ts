export interface EmojiReaction {
  user_id: string;
  user_name: string;
}

export interface Comment {
  id: string;
  content: string;
  entity_id: string;
  entity_type: EntityType;
  user_id: string;
  organization_id?: string;
  created_at: string;
  updated_at: string;
  emojis: Record<string, EmojiReaction[]>;
  user?: {
    id: string;
    name: string;
    email: string;
    picture?: string;
  };
}

export interface CreateCommentRequest {
  content: string;
  entity_type: EntityType;
  entity_id: string;
}

export interface UpdateCommentRequest {
  content: string;
}

export interface CommentReactionRequest {
  emoji: string;
}

export type EntityType =
  | 'Test'
  | 'TestSet'
  | 'TestRun'
  | 'TestResult'
  | 'Metric'
  | 'Model'
  | 'Prompt'
  | 'Behavior'
  | 'Category'
  | 'Task';
