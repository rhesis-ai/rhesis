import { UUID } from 'crypto';
import { EntityType } from '@/types/entity-type';

// Re-exported for backward compatibility; canonical definition lives in
// `@/types/entity-type`.
export { EntityType };

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
