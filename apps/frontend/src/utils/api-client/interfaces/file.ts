import { UUID } from 'crypto';

export type FileEntityType = 'Test' | 'TestResult' | 'Trace' | 'ArchitectSession';

export interface FileResponse {
  id: UUID;
  nano_id?: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  description?: string;
  entity_id: UUID;
  entity_type: FileEntityType;
  position: number;
  user_id?: UUID;
  organization_id?: UUID;
  created_at?: string;
  updated_at?: string;
  // Storage-layer fields (added in cloud-run-large-files migration)
  content_hash?: string;
  extracted_text?: string;
  extraction_status?: 'pending' | 'done' | 'failed' | 'not_applicable';
}
