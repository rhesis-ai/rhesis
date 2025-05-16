import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Category, CategoryCreate, CategoryUpdate, CategoriesQueryParams } from './interfaces/category';
import { UUID } from 'crypto';

export class CategoryClient extends BaseApiClient {
  async getCategories(params: CategoriesQueryParams = {}): Promise<Category[]> {
    const { skip = 0, limit = 100, sort_by = 'created_at', sort_order = 'desc', $filter, entity_type } = params;
    
    // Build query string
    const queryParams = new URLSearchParams();
    queryParams.append('skip', skip.toString());
    queryParams.append('limit', limit.toString());
    queryParams.append('sort_by', sort_by);
    queryParams.append('sort_order', sort_order);
    if ($filter) {
      queryParams.append('$filter', $filter);
    }
    if (entity_type) {
      queryParams.append('entity_type', entity_type);
    }
    
    const url = `${API_ENDPOINTS.categories}?${queryParams.toString()}`;
    
    return this.fetch<Category[]>(url, {
      cache: 'no-store'
    });
  }

  async getCategory(id: UUID): Promise<Category> {
    return this.fetch<Category>(`${API_ENDPOINTS.categories}/${id}`);
  }

  async createCategory(category: CategoryCreate): Promise<Category> {
    return this.fetch<Category>(API_ENDPOINTS.categories, {
      method: 'POST',
      body: JSON.stringify(category),
    });
  }

  async updateCategory(id: UUID, category: CategoryUpdate): Promise<Category> {
    return this.fetch<Category>(`${API_ENDPOINTS.categories}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(category),
    });
  }

  async deleteCategory(id: UUID): Promise<Category> {
    return this.fetch<Category>(`${API_ENDPOINTS.categories}/${id}`, {
      method: 'DELETE',
    });
  }
} 