/* eslint-disable @typescript-eslint/no-non-null-assertion */
import {
  isNotFoundError,
  isDeletedEntityError,
  getNotFoundEntityData,
  getDeletedEntityData,
  getErrorMessage,
} from '../entity-error-handler';

// ============================================================================
// isNotFoundError
// ============================================================================

describe('isNotFoundError', () => {
  it('detects 404 error with data.model_name', () => {
    const error = { status: 404, data: { model_name: 'TestRun' } };
    expect(isNotFoundError(error)).toBe(true);
  });

  it('detects 404 from error message', () => {
    const error = { message: 'API error: 404 - Not found' };
    expect(isNotFoundError(error)).toBe(true);
  });

  it('detects 404 from Next.js digest', () => {
    const error = { digest: 'some-digest', message: 'error 404 occurred' };
    expect(isNotFoundError(error)).toBe(true);
  });

  it('returns false for non-404 errors', () => {
    expect(isNotFoundError({ status: 500 })).toBe(false);
    expect(isNotFoundError({ message: 'Server error' })).toBe(false);
    expect(isNotFoundError(null)).toBe(false);
    expect(isNotFoundError(undefined)).toBe(false);
  });

  it('returns false for 404 without model_name in data', () => {
    expect(isNotFoundError({ status: 404, data: {} })).toBe(false);
  });
});

// ============================================================================
// isDeletedEntityError
// ============================================================================

describe('isDeletedEntityError', () => {
  it('detects 410 error with can_restore flag', () => {
    const error = { status: 410, data: { can_restore: true } };
    expect(isDeletedEntityError(error)).toBe(true);
  });

  it('detects 410 from error message', () => {
    const error = { message: 'API error: 410 - Item deleted' };
    expect(isDeletedEntityError(error)).toBe(true);
  });

  it('detects 410 from Next.js digest', () => {
    const error = { digest: 'some-digest', message: 'error 410 gone' };
    expect(isDeletedEntityError(error)).toBe(true);
  });

  it('returns false for non-410 errors', () => {
    expect(isDeletedEntityError({ status: 404 })).toBe(false);
    expect(isDeletedEntityError({ message: 'Not found' })).toBe(false);
    expect(isDeletedEntityError(null)).toBe(false);
  });

  it('returns false for 410 without can_restore', () => {
    expect(isDeletedEntityError({ status: 410, data: {} })).toBe(false);
  });
});

// ============================================================================
// getNotFoundEntityData
// ============================================================================

describe('getNotFoundEntityData', () => {
  it('returns null for non-404 errors', () => {
    expect(getNotFoundEntityData({ status: 500 })).toBeNull();
  });

  it('extracts data from server-side error with full data object', () => {
    const error = {
      status: 404,
      data: {
        model_name: 'TestRun',
        model_name_display: 'Test Run',
        item_id: 'abc-123',
        table_name: 'test_run',
        list_url: '/test-runs',
        message: 'Test Run not found',
      },
    };

    const result = getNotFoundEntityData(error);
    expect(result).not.toBeNull();
    expect(result!.model_name).toBe('TestRun');
    expect(result!.model_name_display).toBe('Test Run');
    expect(result!.item_id).toBe('abc-123');
    expect(result!.table_name).toBe('test_run');
    expect(result!.list_url).toBe('/test-runs');
  });

  it('parses encoded data from error message (new format)', () => {
    const error = {
      message: 'API error: 404 - table:test_run|id:abc-123|Test Run not found',
    };

    const result = getNotFoundEntityData(error);
    expect(result).not.toBeNull();
    expect(result!.table_name).toBe('test_run');
    expect(result!.item_id).toBe('abc-123');
    expect(result!.model_name).toBe('TestRun');
    expect(result!.model_name_display).toBe('Test Run');
  });

  it('parses encoded data with name field', () => {
    const error = {
      message:
        'API error: 404 - table:project|id:p-1|name:My Project|Project not found',
    };

    const result = getNotFoundEntityData(error);
    expect(result).not.toBeNull();
    expect(result!.table_name).toBe('project');
    expect(result!.item_id).toBe('p-1');
  });
});

// ============================================================================
// getDeletedEntityData
// ============================================================================

describe('getDeletedEntityData', () => {
  it('returns null for non-410 errors', () => {
    expect(getDeletedEntityData({ status: 404 })).toBeNull();
  });

  it('extracts data from client-side error with full data object', () => {
    const error = {
      status: 410,
      data: {
        can_restore: true,
        model_name: 'TestRun',
        model_name_display: 'Test Run',
        item_name: 'My Test Run',
        item_id: 'abc-123',
        table_name: 'test_run',
        restore_url: '/recycle/test_run/abc-123/restore',
        message: 'Test Run has been deleted',
      },
    };

    const result = getDeletedEntityData(error);
    expect(result).not.toBeNull();
    expect(result!.model_name).toBe('TestRun');
    expect(result!.item_name).toBe('My Test Run');
    expect(result!.item_id).toBe('abc-123');
    expect(result!.restore_url).toBe('/recycle/test_run/abc-123/restore');
  });

  it('parses encoded data from error message (new format)', () => {
    const error = {
      message:
        'API error: 410 - table:test_run|id:abc-123|name:My Run|Test Run has been deleted',
    };

    const result = getDeletedEntityData(error);
    expect(result).not.toBeNull();
    expect(result!.table_name).toBe('test_run');
    expect(result!.item_id).toBe('abc-123');
    expect(result!.item_name).toBe('My Run');
    expect(result!.model_name).toBe('TestRun');
    expect(result!.restore_url).toBe('/recycle/test_run/abc-123/restore');
  });

  it('generates user-friendly message for parsed errors', () => {
    const error = {
      message: 'API error: 410 - table:project|id:p-1|Project has been deleted',
    };

    const result = getDeletedEntityData(error);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('deleted');
    expect(result!.message).toContain('restore');
  });
});

// ============================================================================
// getErrorMessage
// ============================================================================

describe('getErrorMessage', () => {
  it('returns message for deleted entity (410)', () => {
    const error = {
      status: 410,
      data: {
        can_restore: true,
        message: 'This item was deleted',
      },
    };
    expect(getErrorMessage(error)).toBe('This item was deleted');
  });

  it('returns message for not found (404)', () => {
    const error = {
      status: 404,
      data: {
        model_name: 'Test',
        message: 'Test not found',
      },
    };
    expect(getErrorMessage(error)).toBe('Test not found');
  });

  it('returns detail from API error data', () => {
    const error = { data: { detail: 'Validation failed' } };
    expect(getErrorMessage(error)).toBe('Validation failed');
  });

  it('stringifies non-string detail', () => {
    const error = { data: { detail: { field: 'error' } } };
    expect(getErrorMessage(error)).toBe('{"field":"error"}');
  });

  it('returns message from Error instances', () => {
    const error = new Error('Something broke');
    expect(getErrorMessage(error)).toBe('Something broke');
  });

  it('returns fallback for unknown error types', () => {
    expect(getErrorMessage(42)).toBe('An unexpected error occurred');
    expect(getErrorMessage(null)).toBe('An unexpected error occurred');
    expect(getErrorMessage({})).toBe('An unexpected error occurred');
  });
});
