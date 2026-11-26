/**
 * Metrics an evaluation framework (DeepEval, Ragas, Garak) defines. Rhesis
 * shows them read-only: their prompt and scoring logic live in the framework,
 * and the backend refuses edits to them.
 */

type BackendTyped = {
  backend_type?: { type_value?: string | null } | null;
};

const DOCS = 'https://docs.rhesis.ai';

/** Display names and docs pages for the frameworks Rhesis ships metrics from. */
const FRAMEWORKS: Record<string, { label: string; docsUrl: string }> = {
  deepeval: { label: 'DeepEval', docsUrl: `${DOCS}/docs/metrics/deepeval` },
  garak: {
    label: 'Garak',
    docsUrl: `${DOCS}/docs/test-sets/import-from-garak`,
  },
  ragas: { label: 'Ragas', docsUrl: `${DOCS}/docs/metrics` },
};

function backendType(metric: BackendTyped): string {
  return metric.backend_type?.type_value?.toLowerCase() ?? '';
}

export function isFrameworkMetric(metric: BackendTyped): boolean {
  const type = backendType(metric);
  return type !== '' && type !== 'rhesis' && type !== 'custom';
}

/** The framework's name and the docs page that covers its metrics. */
export function frameworkInfo(metric: BackendTyped): {
  label: string;
  docsUrl: string;
} {
  const type = backendType(metric);
  return (
    FRAMEWORKS[type] ?? {
      label: type.charAt(0).toUpperCase() + type.slice(1),
      docsUrl: `${DOCS}/docs/metrics`,
    }
  );
}

/**
 * Framework metrics store a marker such as "[deepeval]" in the fields the
 * framework fills in itself (prompt, steps, explanation); it isn't content.
 */
export function isFrameworkPlaceholder(value?: string | null): boolean {
  return /^\[[\w-]+\]$/.test(value?.trim() ?? '');
}
