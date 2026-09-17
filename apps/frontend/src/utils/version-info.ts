import {
  VERSION_INFO_MAX_BYTES,
  VERSION_INFO_MAX_DEPTH,
  type VersionInfoSource,
} from '@/constants/version-info';

export type VersionInfo = Record<string, unknown>;

/** Narrow an untyped attributes value to a usable version object, or null. */
export function asVersionInfo(value: unknown): VersionInfo | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null;
  }
  const record = value as VersionInfo;
  return Object.keys(record).length > 0 ? record : null;
}

const SOURCE_LABELS: Record<VersionInfoSource, string> = {
  endpoint: 'From endpoint configuration',
  response: 'Reported by the endpoint',
  rescore: 'Carried over from the original run',
};

export function versionInfoSourceLabel(source: unknown): string {
  if (typeof source === 'string' && source in SOURCE_LABELS) {
    return SOURCE_LABELS[source as VersionInfoSource];
  }
  return SOURCE_LABELS.endpoint;
}

const MAX_CHIP_VALUE_CHARS = 16;

/**
 * Flatten to `key`/short-display pairs for compact rendering. Nested values collapse to a
 * placeholder rather than being dumped, so a grid cell can never blow up the row height.
 */
export function summarizeVersionInfo(
  info: VersionInfo
): { key: string; display: string }[] {
  return Object.entries(info).map(([key, value]) => {
    let display: string;
    if (Array.isArray(value)) {
      display = `[${value.length}]`;
    } else if (typeof value === 'object' && value !== null) {
      display = '{…}';
    } else {
      display = String(value);
      if (display.length > MAX_CHIP_VALUE_CHARS) {
        display = `${display.slice(0, MAX_CHIP_VALUE_CHARS)}…`;
      }
    }
    return { key, display };
  });
}

function exceedsDepth(value: unknown, maxDepth: number): boolean {
  const stack: { node: unknown; depth: number }[] = [{ node: value, depth: 1 }];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) break;
    const { node, depth } = current;
    // Only containers count toward depth, matching the backend validator.
    if (typeof node !== 'object' || node === null) continue;
    if (depth > maxDepth) return true;
    const children = Array.isArray(node) ? node : Object.values(node);
    for (const child of children) {
      stack.push({ node: child, depth: depth + 1 });
    }
  }
  return false;
}

/**
 * Validate editor text against the backend's rules. Returns an error message, or null when
 * the value is acceptable. Messages match the backend's so both sides read identically.
 */
export function validateVersionInfoDraft(raw: string): string | null {
  const trimmed = raw.trim();
  if (trimmed === '') return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch (error) {
    return error instanceof Error
      ? `Invalid JSON: ${error.message}`
      : 'Invalid JSON';
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return 'version_info must be a JSON object, not an array or a scalar';
  }
  if (exceedsDepth(parsed, VERSION_INFO_MAX_DEPTH)) {
    return `version_info must not nest more than ${VERSION_INFO_MAX_DEPTH} levels deep`;
  }
  const size = new TextEncoder().encode(JSON.stringify(parsed)).length;
  if (size > VERSION_INFO_MAX_BYTES) {
    return `version_info must be at most ${VERSION_INFO_MAX_BYTES} bytes when serialized (received ${size})`;
  }
  return null;
}
