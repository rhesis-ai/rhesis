/**
 * TypeScript interfaces for the file import API.
 */

// ── Analyze (Step 1) ──────────────────────────────────────────────

export interface FileInfo {
  filename: string;
  format: string;
  size_bytes: number;
}

export interface AnalyzeResponse {
  import_id: string;
  file_info: FileInfo;
  headers: string[];
  sample_rows: Record<string, unknown>[];
  suggested_mapping: Record<string, string>;
  confidence: number;
  llm_available: boolean;
}

// ── Parse (Step 2) ────────────────────────────────────────────────

export interface ParseRequest {
  mapping: Record<string, string>;
  test_type: 'Single-Turn' | 'Multi-Turn';
}

export interface ValidationSummary {
  total_rows: number;
  valid_rows: number;
  error_count: number;
  warning_count: number;
  error_types: Record<string, number>;
}

export interface ValidationError {
  type: string;
  field: string;
  message: string;
}

export interface PreviewRow {
  index: number;
  data: Record<string, unknown>;
  errors: ValidationError[];
  warnings: ValidationError[];
}

export interface PreviewPage {
  rows: PreviewRow[];
  page: number;
  page_size: number;
  total_rows: number;
  total_pages: number;
}

export interface ParseResponse {
  total_rows: number;
  validation_summary: ValidationSummary;
  preview: PreviewPage;
}

// ── Confirm (Step 3) ──────────────────────────────────────────────

export interface ConfirmRequest {
  name?: string;
  description?: string;
  short_description?: string;
}

export interface ConfirmResponse {
  id: string;
  name: string;
  description?: string;
  short_description?: string;
}

// ── Re-map ────────────────────────────────────────────────────────

export interface RemapResponse {
  mapping: Record<string, string>;
  confidence: number;
  llm_available: boolean;
  message?: string;
}

// ── Cancel ────────────────────────────────────────────────────────

export interface CancelResponse {
  status: string;
  import_id: string;
}
