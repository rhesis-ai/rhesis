/**
 * Reading an invoker failure out of a test result's `test_output`.
 *
 * The backend records a failed target call in one of two shapes, and before this existed
 * every consumer guessed at one of them: a flat error object for single-turn, or nested
 * under the first `send_message_to_target` turn for multi-turn (Penelope). Nothing in the
 * frontend read the nested one at all, so a multi-turn test whose endpoint rejected the
 * very first message displayed "No evaluation reasoning available".
 *
 * Mirrors `apps/backend/src/rhesis/backend/app/utils/response_extractor.py` --
 * `is_endpoint_failure` / `get_endpoint_error_details` / `summarize_endpoint_failure`.
 * Keep the two in step.
 */

import {
  TestOutput,
  PenelopeTurn,
} from '@/utils/api-client/interfaces/test-results';

export interface EndpointFailure {
  /** HTTP status, when the failure carried one. Absent for SDK/connector and network errors. */
  statusCode?: number;
  /** Invoker category, e.g. `http_error`, `sdk_timeout`, `network_error`. */
  errorType?: string;
  /** HTTP reason phrase, e.g. "Bad Request". */
  reason?: string;
  /** The target's own words about why it refused. */
  message: string;
  /** The target's raw response body, which is usually where the real reason is. */
  responseBody?: string;
  /** One-line summary suitable for a tooltip or a banner heading. */
  summary: string;
}

type RawOutput = Record<string, unknown>;

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  // Status codes arrive as strings from some invokers.
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() !== '' ? value : undefined;
}

/**
 * Whether this object is an invoker failure.
 *
 * `error_type` is required alongside `error` so a target whose own mapped response happens
 * to contain an `error` field is not mistaken for a failed invocation.
 */
function isFailureShape(output: RawOutput): boolean {
  if (output.error_type === 'http_error') return true;

  const statusCode = asNumber(output.status_code);
  if (output.error && statusCode !== undefined && statusCode >= 400)
    return true;

  return Boolean(output.error) && Boolean(output.error_type);
}

/** Pull the invoker's error object out of a Penelope trace's first target interaction. */
function nestedFailure(
  history: PenelopeTurn[] | undefined
): RawOutput | undefined {
  if (!Array.isArray(history)) return undefined;

  for (const turn of history) {
    const interaction = turn?.target_interaction;
    if (interaction?.tool_name !== 'send_message_to_target') continue;

    const content = interaction.tool_message?.content;
    let parsed: unknown = content;
    if (typeof content === 'string') {
      try {
        parsed = JSON.parse(content);
      } catch {
        return undefined;
      }
    }
    if (!parsed || typeof parsed !== 'object') return undefined;

    const metadata = (parsed as RawOutput).metadata;
    if (!metadata || typeof metadata !== 'object') return undefined;

    const details = (metadata as RawOutput).error_details;
    if (!details || typeof details !== 'object') return undefined;

    return details as RawOutput;
  }

  // Only the first target turn is inspected, matching the backend: a later turn failing is
  // left to normal Pass/Fail scoring rather than voiding the whole conversation.
  return undefined;
}

function buildSummary(statusCode: number | undefined, message: string): string {
  const label = statusCode !== undefined ? `HTTP ${statusCode}` : 'an error';
  const base = `Endpoint returned ${label}`;
  if (!message) return base;
  // The invoker's text usually already names the status; don't say it twice.
  if (statusCode !== undefined && message.includes(String(statusCode))) {
    return message;
  }
  return `${base}: ${message}`;
}

/**
 * Describe the target's failure, or `null` when the call did not fail.
 *
 * Usable as both the test and the value: `const failure = getEndpointFailure(output)`.
 */
export function getEndpointFailure(
  testOutput: TestOutput | undefined | null
): EndpointFailure | null {
  if (!testOutput) return null;

  const output = testOutput as unknown as RawOutput;
  const details = isFailureShape(output)
    ? output
    : nestedFailure(testOutput.history);

  if (!details || !isFailureShape(details)) return null;

  const statusCode = asNumber(details.status_code);
  const message =
    asString(details.output) ??
    asString(details.message) ??
    asString(details.error) ??
    '';

  return {
    statusCode,
    errorType: asString(details.error_type),
    reason: asString(details.reason),
    message,
    // response_body is only present on rows written before the invokers were normalised
    // onto response_content; read both so old runs still show their body.
    responseBody:
      asString(details.response_content) ?? asString(details.response_body),
    summary: buildSummary(statusCode, message),
  };
}
