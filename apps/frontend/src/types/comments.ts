export interface Comment {
  id: string;
  comment_text: string;
  entity_id: string;
  entity_type: string;
  user_id: string;
  organization_id: string;
  created_at: string;
  updated_at: string;
  emojis: Record<string, number>;
  user?: {
    id: string;
    name: string;
    email: string;
  };
}

export interface CreateCommentRequest {
  comment_text: string;
  entity_type: string;
  entity_id: string;
}

export interface UpdateCommentRequest {
  comment_text: string;
}

export interface CommentReactionRequest {
  emoji: string;
}

export type EntityType = 'test' | 'test_set' | 'test_run' | 'metric' | 'model' | 'prompt' | 'behavior' | 'category';
