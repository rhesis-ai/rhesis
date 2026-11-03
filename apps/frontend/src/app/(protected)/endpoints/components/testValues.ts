import { AUTO_FILLED_VARS } from './mapping-variables';
import {
  buildCurl,
  extractVars,
  substituteVars,
} from './endpoint-template-utils';

export type TestValues = Record<string, unknown>;

/** What the wizard's test requests send until the user types their own values. */
export const DEFAULT_TEST_VALUES: TestValues = { input: 'Hello, how are you?' };

const FILE_VAR_RE = /^(files?|images?)$/i;

export const isFileVar = (name: string) => FILE_VAR_RE.test(name);

/** The template variables a test request needs a value for. */
export function testValueVars(reqBody: string): string[] {
  return extractVars(reqBody).filter(v => !AUTO_FILLED_VARS.has(v));
}

/** Typed values as the test call's input_data, leaving out empty ones. */
export function testInputData(values: TestValues): Record<string, unknown> {
  const inputData: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(values)) {
    if (v === '' || v === undefined) continue;
    // Typed text is one user turn; JSON input can pass a full history instead.
    inputData[k] =
      k === 'messages' && typeof v === 'string'
        ? [{ role: 'user', content: v }]
        : v;
  }
  return inputData;
}

export function formatTestValue(value: unknown): string {
  if (value === undefined) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

/** The request a test sends, as cURL; the auth token stays hidden. */
export function buildTestCurl({
  method,
  url,
  requestHeaders,
  reqBody,
  values,
}: {
  method: string;
  url: string;
  requestHeaders?: string;
  reqBody: string;
  values: TestValues;
}): string {
  let headers: Record<string, unknown> = {};
  try {
    headers = JSON.parse(requestHeaders || '{}') as Record<string, unknown>;
  } catch {
    // Unparseable headers show as none; the Connection step flags them.
  }
  const shownHeaders = Object.fromEntries(
    Object.entries(headers).map(([k, v]) => [
      k,
      String(v).replace(/\{\{\s*auth_token\s*\}\}/g, '[hidden]'),
    ])
  );
  const previewValues = Object.fromEntries(
    Object.entries(values).map(([k, v]) => [k, formatTestValue(v)])
  );
  return buildCurl(
    method || 'POST',
    url || '—',
    shownHeaders,
    substituteVars(reqBody || '{}', previewValues)
  );
}
