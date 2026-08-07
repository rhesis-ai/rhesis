export function buildTestRunSummarizeSessionTitle(input: {
  testRunName: string;
}): string {
  const name = input.testRunName.trim() || 'Test Run';
  return `Test run summary — ${name}`;
}

export interface BuildTestRunSummarizePromptInput {
  testRunId: string;
  testRunName: string;
  endpointName?: string;
  testSetName?: string;
}

export function buildTestRunSummarizePrompt(
  input: BuildTestRunSummarizePromptInput
): string {
  const lines = [
    'Summarize this test run for me.',
    '',
    'This is a Test Run handoff — analyze these test results; do not show the menu',
    'and do not start exploration or create entities.',
    '',
    `Test run: ${input.testRunName.trim() || 'unnamed'}`,
    `Test run ID: ${input.testRunId}`,
    `Endpoint: ${input.endpointName?.trim() || 'unknown'}`,
    `Test set: ${input.testSetName?.trim() || 'unknown'}`,
    '',
    'Please re-fetch stats for this run, summarize overall and by behavior/metric,',
    'then sample a few failed results and call out patterns and next steps.',
  ];

  return lines.join('\n');
}
