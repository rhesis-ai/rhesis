import { UUID } from 'crypto';
import { EntityType } from '@/types/entity-type';

export type FileEntityType =
  | typeof EntityType.TEST
  | typeof EntityType.TEST_RESULT
  | typeof EntityType.TRACE
  | 'ArchitectSession';

export interface FileResponse {
  id: UUID;
  filename: string;
  content_type: string;
  size_bytes: number;
}
