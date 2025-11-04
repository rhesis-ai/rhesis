import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  TypeLookup,
  TypeLookupCreate,
  TypeLookupUpdate,
  TypeLookupsQueryParams,
} from './interfaces/type-lookup';

export class TypeLookupClient extends BaseApiClient {
  async getTypeLookups(
    params: TypeLookupsQueryParams = {}
  ): Promise<TypeLookup[]> {
    const {
      skip,
      limit,
      sort_by = 'created_at',
      sort_order = 'desc',
      $filter,
    } = params;

    // Build query string
    const queryParams = new URLSearchParams();
    if (skip !== undefined) queryParams.append('skip', skip.toString());
    if (limit !== undefined) queryParams.append('limit', limit.toString());
    queryParams.append('sort_by', sort_by);
    queryParams.append('sort_order', sort_order);
    if ($filter) {
      // Don't double encode - just use the filter as is
      queryParams.append('$filter', $filter);
    }

    const queryString = queryParams.toString();
    const url = `${API_ENDPOINTS.type_lookups}?${queryString}`;

    return this.fetch<TypeLookup[]>(url, {
      cache: 'no-store',
    });
  }

  async getTypeLookup(id: string): Promise<TypeLookup> {
    return this.fetch<TypeLookup>(`${API_ENDPOINTS.type_lookups}/${id}`);
  }

  async createTypeLookup(typeLookup: TypeLookupCreate): Promise<TypeLookup> {
    return this.fetch<TypeLookup>(API_ENDPOINTS.type_lookups, {
      method: 'POST',
      body: JSON.stringify(typeLookup),
    });
  }

  async updateTypeLookup(
    id: string,
    typeLookup: TypeLookupUpdate
  ): Promise<TypeLookup> {
    return this.fetch<TypeLookup>(`${API_ENDPOINTS.type_lookups}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(typeLookup),
    });
  }

  async deleteTypeLookup(id: string): Promise<TypeLookup> {
    return this.fetch<TypeLookup>(`${API_ENDPOINTS.type_lookups}/${id}`, {
      method: 'DELETE',
    });
  }
}
