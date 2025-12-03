import { UUID } from 'crypto';

// Base interface for type lookups
export interface TypeLookupBase {
  type_name: string;
  type_value: string;
  description?: string;
  organization_id?: UUID;
  user_id?: UUID | null;
}

export type TypeLookupCreate = TypeLookupBase;

export type TypeLookupUpdate = Partial<TypeLookupBase>;

export interface TypeLookup extends TypeLookupBase {
  id: UUID;
}

export interface TypeLookupsQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  $filter?: string;
}
