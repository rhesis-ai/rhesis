import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { asVersionInfo } from '@/utils/version-info';

/** Span attribute carrying the version of the system behind the endpoint. */
export const VERSION_INFO_ATTRIBUTE = 'endpoint.version_info';

/** Span attributes are flat strings, so the version arrives as serialized JSON. */
export function parseVersionInfo(
  value: unknown
): Record<string, unknown> | null {
  if (typeof value !== 'string') return asVersionInfo(value);
  try {
    return asVersionInfo(JSON.parse(value));
  } catch {
    return null;
  }
}

export function parseIfJSON(value: unknown): unknown {
  if (
    typeof value === 'string' &&
    (value.startsWith('[') || value.startsWith('{'))
  ) {
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }
  return value;
}

export interface LlmMessage {
  role: string;
  content: unknown;
}

export interface SpanIO {
  kind: 'function' | 'llm' | 'tool' | 'agent';
  /** Function spans split positional and keyword arguments. */
  input: { label?: string; value: unknown }[];
  /** Set for LLM spans, whose input is a list of prompt messages. */
  messages: LlmMessage[] | null;
  output: unknown;
}

export interface SpanAttributeGroups {
  llm: Record<string, unknown>;
  function: Record<string, unknown>;
  test: Record<string, unknown>;
  other: Record<string, unknown>;
  versionInfo: Record<string, unknown> | null;
}

// Shown in the I/O panes or the span header, so left out of the attribute lists.
const IO_ATTRIBUTE_KEYS = new Set([
  'function.args',
  'function.kwargs',
  'function.result',
  'function.result_preview',
  'ai.agent.input',
  'ai.agent.output',
  'ai.llm.tokens.input',
  'ai.llm.tokens.output',
  'ai.llm.tokens.total',
]);

export function groupAttributes(
  attrs: Record<string, unknown> | undefined
): SpanAttributeGroups {
  const groups: SpanAttributeGroups = {
    llm: {},
    function: {},
    test: {},
    other: {},
    versionInfo: null,
  };
  if (!attrs) return groups;

  for (const [key, value] of Object.entries(attrs)) {
    if (key === VERSION_INFO_ATTRIBUTE || IO_ATTRIBUTE_KEYS.has(key)) continue;
    if (key.startsWith('ai.') || key.startsWith('llm.'))
      groups.llm[key] = value;
    else if (key.startsWith('function.')) groups.function[key] = value;
    else if (key.startsWith('rhesis.test.')) groups.test[key] = value;
    else groups.other[key] = value;
  }
  groups.versionInfo = parseVersionInfo(attrs[VERSION_INFO_ATTRIBUTE]);
  return groups;
}

function eventAttr(span: SpanNode, eventName: string, attr: string): unknown {
  return span.events?.find(e => e.name === eventName)?.attributes?.[attr];
}

const present = (value: unknown) =>
  value !== undefined && value !== null && value !== '';

/** `[]` and `{}` arguments say nothing, so they get no row. */
function hasContent(value: unknown): boolean {
  if (!present(value)) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value as object).length > 0;
  return true;
}

/**
 * Every input/output a span carries, one entry per kind. Usually one, but an
 * instrumented function that is also an agent can carry both.
 */
export function extractSpanIO(span: SpanNode): SpanIO[] {
  const attrs = span.attributes ?? {};
  const result: SpanIO[] = [];

  const args = parseIfJSON(attrs['function.args']);
  const kwargs = parseIfJSON(attrs['function.kwargs']);
  const fnOutput = attrs['function.result'] || attrs['function.result_preview'];
  if (hasContent(args) || hasContent(kwargs) || present(fnOutput)) {
    const input: SpanIO['input'] = [];
    // Labelled only when both kinds are there; one alone is just "the input".
    const both = hasContent(args) && hasContent(kwargs);
    if (hasContent(args))
      input.push({ label: both ? 'Positional' : undefined, value: args });
    if (hasContent(kwargs))
      input.push({ label: both ? 'Keyword' : undefined, value: kwargs });
    result.push({
      kind: 'function',
      input,
      messages: null,
      output: present(fnOutput) ? parseIfJSON(fnOutput) : null,
    });
  }

  const prompts = span.events?.filter(e => e.name === 'ai.prompt') ?? [];
  const completion = eventAttr(span, 'ai.completion', 'ai.completion.content');
  if (prompts.length > 0 || present(completion)) {
    result.push({
      kind: 'llm',
      input: [],
      messages: prompts.map(e => ({
        role: String(e.attributes?.['ai.prompt.role'] ?? 'unknown'),
        content: e.attributes?.['ai.prompt.content'],
      })),
      output: present(completion) ? parseIfJSON(String(completion)) : null,
    });
  }

  const toolIn = eventAttr(span, 'ai.tool.input', 'ai.tool.input');
  const toolOut = eventAttr(span, 'ai.tool.output', 'ai.tool.output');
  if (present(toolIn) || present(toolOut)) {
    result.push({
      kind: 'tool',
      input: present(toolIn) ? [{ value: parseIfJSON(String(toolIn)) }] : [],
      messages: null,
      output: present(toolOut) ? parseIfJSON(String(toolOut)) : null,
    });
  }

  const agentIn =
    attrs['ai.agent.input'] ||
    eventAttr(span, 'ai.agent.input', 'ai.agent.input');
  const agentOut =
    attrs['ai.agent.output'] ||
    eventAttr(span, 'ai.agent.output', 'ai.agent.output');
  if (present(agentIn) || present(agentOut)) {
    result.push({
      kind: 'agent',
      input: present(agentIn) ? [{ value: parseIfJSON(String(agentIn)) }] : [],
      messages: null,
      output: present(agentOut) ? parseIfJSON(String(agentOut)) : null,
    });
  }

  return result;
}
