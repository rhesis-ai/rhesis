import { UUID } from 'crypto';
import { User } from './user';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { PaginationParams } from './pagination';
import { Tag } from './tag';

/** Known fields in source_metadata - extensible via index signature */
export interface SourceMetadata {
  source_type?: string;
  provider?: string;
  original_filename?: string;
  file_size?: number;
  url?: string;
  mcp_tool_id?: string;
  mcp_id?: string;
  [key: string]: unknown;
}

export interface Source {
  id: UUID;
  title: string;
  description?: string;
  // Note: content is only included when fetched via /sources/{id}/content endpoint
  content?: string;
  source_type_id?: UUID;
  url?: string;
  citation?: string;
  language_code?: string;
  source_metadata?: SourceMetadata;
  tags?: Tag[];
  created_at?: string;
  updated_at?: string;
  counts?: {
    comments: number;
    tasks: number;
  };

  // References
  source_type?: TypeLookup;
  status?: Status;
  user?: User; // uploader/creator of the source
  owner?: User;
  assignee?: User;
}

export interface SourceCreate {
  title: string;
  description?: string;
  content?: string;
  source_type_id?: UUID;
  url?: string;
  citation?: string;
  language_code?: string;
  source_metadata?: SourceMetadata;
  tags?: Tag[];
}

export interface SourceUpdate {
  title?: string;
  description?: string;
  content?: string;
  source_type_id?: UUID;
  url?: string;
  citation?: string;
  language_code?: string;
  source_metadata?: SourceMetadata;
  tags?: Tag[];
}

export interface SourcesQueryParams extends PaginationParams {
  $filter?: string;
  source_type_id?: UUID;
}
