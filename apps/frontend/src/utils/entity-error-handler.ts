/**
 * Entity Error Handler
 * 
 * Centralized utilities for handling entity-specific errors (404, 410).
 * This module provides type-safe error detection and data extraction for:
 * - 404 Not Found: Entity doesn't exist or no permission
 * - 410 Gone: Entity was soft-deleted and can be restored
 */

import { DeletedEntityData } from '@/components/common/DeletedEntityAlert';

export interface NotFoundEntityData {
  model_name: string;
  model_name_display?: string;
  item_id: string;
  table_name: string;
  list_url: string;
  message: string;
}

// ============================================================================
// 404 Not Found Error Handling
// ============================================================================

/**
 * Check if an error is a 404 Not Found response.
 * 
 * @param error - The error object to check
 * @returns True if the error is a not found error
 */
export function isNotFoundError(error: any): boolean {
  // Check if error has status 404
  if (error?.status === 404 && error?.data?.model_name) {
    return true;
  }
  
  // Fallback: Check error message for 404 status
  if (error?.message?.includes('API error: 404')) {
    return true;
  }
  
  // Check digest for Next.js serialized errors
  if (error?.digest && error?.message?.includes('404')) {
    return true;
  }
  
  return false;
}

/**
 * Extract not found entity data from a 404 Not Found error response.
 * 
 * @param error - The error object from the API
 * @returns Not found entity data or null if not applicable
 */
export function getNotFoundEntityData(error: any): NotFoundEntityData | null {
  if (!isNotFoundError(error)) {
    return null;
  }

  // If we have the full data object (server-side before serialization), use it
  if (error.data?.model_name) {
    const data = error.data;
    return {
      model_name: data.model_name,
      model_name_display: data.model_name_display,
      item_id: data.item_id,
      table_name: data.table_name,
      list_url: data.list_url,
      message: data.message || data.detail,
    };
  }

  // Fallback: Parse from error message (after serialization across boundary)
  // Error message format: "API error: 404 - Test Run not found"
  const message = error.message || '';
  const match = message.match(/404 - (.+?) not found/);
  
  if (match) {
    const modelNameDisplay = match[1]; // "Test Run"
    const modelName = modelNameDisplay.replace(/\s+/g, ''); // "TestRun"
    
    // Try to get item_id and table_name from current URL
    let itemId = '';
    let tableName = '';
    
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;
      const segments = path.split('/').filter(Boolean);
      
      // URL format: /test-runs/uuid or /tests/uuid
      if (segments.length >= 2) {
        tableName = segments[0].replace(/-/g, '_'); // test-runs -> test_run
        itemId = segments[1];
      }
    }
    
    const listUrl = `/${tableName.replace(/_/g, '-')}`;
    
    return {
      model_name: modelName,
      model_name_display: modelNameDisplay,
      item_id: itemId,
      table_name: tableName || modelName.toLowerCase(),
      list_url: listUrl,
      message: `The ${modelNameDisplay.toLowerCase()} you're looking for doesn't exist or you don't have permission to access it.`,
    };
  }

  return null;
}

// ============================================================================
// 410 Gone (Deleted Entity) Error Handling
// ============================================================================

/**
 * Check if an error is a 410 Gone response for a deleted entity.
 * 
 * @param error - The error object to check
 * @returns True if the error is a deleted entity error
 */
export function isDeletedEntityError(error: any): boolean {
  // Check if error has status and data (client-side error)
  if (error?.status === 410 && error?.data?.can_restore === true) {
    return true;
  }
  
  // Fallback: Check error message for 410 status (server-side error that crossed boundary)
  if (error?.message?.includes('API error: 410')) {
    return true;
  }
  
  // Check digest for Next.js serialized errors
  if (error?.digest && error?.message?.includes('410')) {
    return true;
  }
  
  return false;
}

/**
 * Extract deleted entity data from a 410 Gone error response.
 * 
 * @param error - The error object from the API
 * @returns Deleted entity data or null if not applicable
 */
export function getDeletedEntityData(error: any): DeletedEntityData | null {
  if (!isDeletedEntityError(error)) {
    return null;
  }

  // If we have the full data object (client-side error), use it
  if (error.data?.model_name) {
    const data = error.data;
    return {
      model_name: data.model_name,
      model_name_display: data.model_name_display,
      item_name: data.item_name,
      item_id: data.item_id,
      table_name: data.table_name,
      restore_url: data.restore_url,
      message: data.message || data.detail,
    };
  }

  // Fallback: Parse from error message (server-side error that crossed boundary)
  // Error message format: "API error: 410 - Test Run has been deleted"
  // Or with item name: "API error: 410 - My Test Run | Test Run has been deleted"
  const message = error.message || '';
  
  // Try to extract item name if present (format: "item_name | message")
  let itemName: string | undefined;
  let cleanMessage = message;
  const itemNameMatch = message.match(/410 - (.+?) \| (.+?) has been deleted/);
  
  if (itemNameMatch) {
    // Message includes item name
    itemName = itemNameMatch[1].trim();
    cleanMessage = message.replace(`${itemName} | `, ''); // Remove item name from message
  }
  
  const match = cleanMessage.match(/410 - (.+?) has been deleted/);
  
  if (match) {
    const modelNameDisplay = match[1]; // "Test Run"
    const modelName = modelNameDisplay.replace(/\s+/g, ''); // "TestRun"
    
    // Try to get item_id and table_name from current URL
    let itemId = '';
    let tableName = '';
    
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;
      const segments = path.split('/').filter(Boolean);
      
      // URL format: /test-runs/uuid or /tests/uuid
      if (segments.length >= 2) {
        tableName = segments[0].replace(/-/g, '_'); // test-runs -> test_run
        itemId = segments[1];
      }
    }
    
    return {
      model_name: modelName,
      model_name_display: modelNameDisplay,
      item_name: itemName, // Now includes item name if it was in the message
      item_id: itemId,
      table_name: tableName || modelName.toLowerCase(),
      restore_url: `/recycle/${tableName}/${itemId}/restore`,
      message: `This ${modelNameDisplay.toLowerCase()} has been deleted. You can restore it from the recycle bin.`,
    };
  }

  return null;
}

// ============================================================================
// General Error Message Handling
// ============================================================================

/**
 * Get a user-friendly error message from any error.
 * Handles deleted entities, not found errors, API errors, and generic errors.
 * 
 * @param error - The error object
 * @returns User-friendly error message
 */
export function getErrorMessage(error: any): string {
  // Check if it's a deleted entity (410)
  if (isDeletedEntityError(error)) {
    return error.data?.message || error.data?.detail || 'This item has been deleted.';
  }

  // Check if it's a not found error (404)
  if (isNotFoundError(error)) {
    return error.data?.message || error.data?.detail || 'The item you\'re looking for was not found.';
  }

  // Check for API error with detail
  if (error?.data?.detail) {
    return typeof error.data.detail === 'string'
      ? error.data.detail
      : JSON.stringify(error.data.detail);
  }

  // Check for standard Error object
  if (error instanceof Error) {
    return error.message;
  }

  // Fallback
  return 'An unexpected error occurred';
}

