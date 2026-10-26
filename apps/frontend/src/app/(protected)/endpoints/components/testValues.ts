import { AUTO_FILLED_VARS } from './mapping-variables';
import { extractVars } from './endpoint-template-utils';

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
