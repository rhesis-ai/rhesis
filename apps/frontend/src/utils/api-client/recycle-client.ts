import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';

/**
 * Client for managing soft-deleted items in the recycle bin.
 */
export class RecycleClient extends BaseApiClient {
  /**
   * Restore a soft-deleted item from the recycle bin.
   *
   * @param tableName - The singular table name of the model (e.g., 'test_run', 'test', 'project')
   * @param itemId - The UUID of the item to restore
   * @returns Promise with the restored item
   */
  async restoreItem(tableName: string, itemId: string): Promise<any> {
    return this.fetch(`/recycle/${tableName}/${itemId}/restore`, {
      method: 'POST',
    });
  }

  /**
   * Get soft-deleted items for a specific model.
   *
   * @param tableName - The table name of the model
   * @param skip - Number of records to skip
   * @param limit - Maximum number of records to return
   * @returns Promise with paginated deleted items
   */
  async getDeletedItems(
    tableName: string,
    skip: number = 0,
    limit: number = 100
  ): Promise<{
    model: string;
    count: number;
    items: any[];
    has_more: boolean;
  }> {
    return this.fetch(`/recycle/${tableName}?skip=${skip}&limit=${limit}`, {
      method: 'GET',
    });
  }

  /**
   * Get counts of deleted items across all models.
   *
   * @returns Promise with counts per model
   */
  async getRecycleBinCounts(): Promise<{
    total_models_with_deleted: number;
    counts: Record<string, { count: number; class_name: string }>;
  }> {
    return this.fetch('/recycle/stats/counts', {
      method: 'GET',
    });
  }

  /**
   * Permanently delete an item from the recycle bin.
   *
   * @param tableName - The table name of the model
   * @param itemId - The UUID of the item to permanently delete
   * @returns Promise with success message
   */
  async permanentlyDeleteItem(
    tableName: string,
    itemId: string
  ): Promise<{ message: string; warning: string }> {
    return this.fetch(`/recycle/${tableName}/${itemId}?confirm=true`, {
      method: 'DELETE',
    });
  }
}
