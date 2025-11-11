import { UUID } from 'crypto';
import { User } from './user';
import { TypeLookup } from './type-lookup';
import { Status } from './status';
import { PaginationParams } from './pagination';

export interface Tag {
  id: UUID;
  name: string;
  icon_unicode?: string;
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
  source_metadata?: Record<string, any>;
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
  source_metadata?: Record<string, any>;
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
  source_metadata?: Record<string, any>;
  tags?: Tag[];
}

export interface SourcesQueryParams extends PaginationParams {
  $filter?: string;
  source_type_id?: UUID;
}
