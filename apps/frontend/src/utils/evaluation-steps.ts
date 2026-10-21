const STEP_SEPARATOR = '\n---\n';
const SEPARATOR_PATTERN = /\r?\n[ \t]*---[ \t]*\r?\n/;
// "Step 1:", "1.", "1)" at the start of a step. Needs whitespace after the
// mark so text like "2.5 points" isn't stripped.
const STEP_PREFIX = /^\s*(?:step\s+)?\d+\s*[.):](?:\s+|$)/i;
const NUMBERED_LINE = /^\s*(?:step\s+)?(\d+)\s*[.):]\s+\S/i;

// Twice, because steps split by hand in the UI can carry both: "Step 1:\n1. ..."
function stripStepPrefix(step: string): string {
  return step.replace(STEP_PREFIX, '').replace(STEP_PREFIX, '').trim();
}

// API, Architect and seed metrics store a plain "1. ...\n2. ..." list. Only
// treat text as a list when it opens with step 1, so free-text rubrics stay
// one step.
function splitNumberedList(text: string): string[] | null {
  const lines = text.trim().split(/\r?\n/);
  if (NUMBERED_LINE.exec(lines[0])?.[1] !== '1') return null;

  const steps: string[] = [];
  let expected = 1;
  for (const line of lines) {
    if (NUMBERED_LINE.exec(line)?.[1] === String(expected)) {
      steps.push(line);
      expected += 1;
    } else {
      steps[steps.length - 1] += `\n${line}`;
    }
  }
  return steps.length > 1 ? steps : null;
}

/**
 * Splits stored evaluation steps into the text of each step, without its
 * "Step N:" or "N." prefix. Accepts the UI's "---"-separated format and plain
 * numbered lists.
 */
export function parseEvaluationSteps(
  value: string | null | undefined
): string[] {
  if (!value?.trim()) return [];
  const parts = SEPARATOR_PATTERN.test(value)
    ? value.split(SEPARATOR_PATTERN)
    : (splitNumberedList(value) ?? [value]);
  return parts.map(stripStepPrefix).filter(Boolean);
}

export function formatEvaluationSteps(steps: string[]): string {
  return steps
    .map(step => step.trim())
    .filter(Boolean)
    .map((step, index) => `Step ${index + 1}:\n${step}`)
    .join(STEP_SEPARATOR);
}
