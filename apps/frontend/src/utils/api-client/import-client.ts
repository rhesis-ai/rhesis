import { BaseApiClient } from './base-client';
import type {
  AnalyzeResponse,
  CancelResponse,
  ConfirmRequest,
  ConfirmResponse,
  ParseRequest,
  ParseResponse,
  PreviewPage,
  RemapResponse,
} from './interfaces/import';

const IMPORT_PREFIX = '/import';

/**
 * API client for the file import flow.
 *
 * Supports the multi-step import process:
 *   1. analyzeFile   – upload + detect mapping
 *   2. parseWithMapping – apply mapping + full parse
 *   3. getPreviewPage   – paginated preview
 *   4. confirmImport    – create test set
 *   5. cancelImport     – clean up
 *   6. remapWithLlm     – re-run mapping with AI
 */
export class ImportClient extends BaseApiClient {
  /**
   * Step 1: Upload a file and get suggested column mapping.
   *
   * Uses multipart/form-data (browser sets Content-Type automatically).
   */
  async analyzeFile(file: File): Promise<AnalyzeResponse> {
    const url = new URL(`${this.baseUrl}${IMPORT_PREFIX}/analyze`);

    const formData = new FormData();
    formData.append('file', file);

    // Multipart upload: omit Content-Type so browser sets boundary
    const headers: Record<string, string> = {};
    if (this.sessionToken) {
      headers['Authorization'] = `Bearer ${this.sessionToken}`;
    }

    const response = await fetch(url.toString(), {
      method: 'POST',
      body: formData,
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const err = new Error('Upload failed') as Error & {
        status?: number;
        data?: unknown;
      };
      err.status = response.status;
      err.data = {
        detail: errorData?.detail ?? `Upload failed (${response.status})`,
      };
      throw err;
    }

    return response.json();
  }

  /**
   * Step 2: Parse the file with confirmed column mapping.
   */
  async parseWithMapping(
    importId: string,
    mapping: Record<string, string>,
    testType: 'Single-Turn' | 'Multi-Turn' = 'Single-Turn'
  ): Promise<ParseResponse> {
    const body: ParseRequest = { mapping, test_type: testType };
    return this.fetch<ParseResponse>(`${IMPORT_PREFIX}/${importId}/parse`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /**
   * Step 3: Get a page of parsed preview data.
   */
  async getPreviewPage(
    importId: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<PreviewPage> {
    return this.fetch<PreviewPage>(
      `${IMPORT_PREFIX}/${importId}/preview?page=${page}&page_size=${pageSize}`
    );
  }

  /**
   * Step 4: Confirm import and create the test set.
   */
  async confirmImport(
    importId: string,
    options: ConfirmRequest = {}
  ): Promise<ConfirmResponse> {
    return this.fetch<ConfirmResponse>(`${IMPORT_PREFIX}/${importId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(options),
    });
  }

  /**
   * Step 5: Cancel and clean up an import session.
   */
  async cancelImport(importId: string): Promise<CancelResponse> {
    return this.fetch<CancelResponse>(`${IMPORT_PREFIX}/${importId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Re-run column mapping using LLM assistance.
   *
   * Returns the existing mapping with llm_available=false if no LLM
   * is configured.
   */
  async remapWithLlm(importId: string): Promise<RemapResponse> {
    return this.fetch<RemapResponse>(`${IMPORT_PREFIX}/${importId}/remap`, {
      method: 'POST',
    });
  }
}
