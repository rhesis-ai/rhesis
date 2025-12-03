import { UUID } from 'crypto';

export interface CategoryBase {
  name: string;
  description?: string | null;
  status_id?: UUID | null;
  user_id?: UUID | null;
  organization_id?: UUID | null;
}

export type CategoryCreate = CategoryBase;

export type CategoryUpdate = Partial<CategoryBase>;

export interface Category extends CategoryBase {
  id: UUID;
}

export interface CategoriesQueryParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: string;
  $filter?: string;
  entity_type?: string;
}
