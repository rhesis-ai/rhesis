import {
  buildTestRunSummarizePrompt,
  buildTestRunSummarizeSessionTitle,
} from '../test-run-summarize-prompt';

describe('buildTestRunSummarizeSessionTitle', () => {
  it('includes the test run name', () => {
    expect(
      buildTestRunSummarizeSessionTitle({ testRunName: 'Nightly Safety' })
    ).toBe('Test run summary — Nightly Safety');
  });

  it('falls back when the name is blank', () => {
    expect(buildTestRunSummarizeSessionTitle({ testRunName: '  ' })).toBe(
      'Test run summary — Test Run'
    );
  });
});

describe('buildTestRunSummarizePrompt', () => {
  it('includes run identity, endpoint, test set, and handoff guardrails', () => {
    const prompt = buildTestRunSummarizePrompt({
      testRunId: 'run-abc',
      testRunName: 'Nightly Safety',
      endpointName: 'Chatbot',
      testSetName: 'Safety Suite',
    });

    expect(prompt).toContain('Summarize this test run');
    expect(prompt).toContain('Test Run handoff');
    expect(prompt).toContain('do not show the menu');
    expect(prompt).toContain('Test run: Nightly Safety');
    expect(prompt).toContain('Test run ID: run-abc');
    expect(prompt).toContain('Endpoint: Chatbot');
    expect(prompt).toContain('Test set: Safety Suite');
    expect(prompt).toContain('re-fetch stats');
  });

  it('uses unknown fallbacks when endpoint/test set are missing', () => {
    const prompt = buildTestRunSummarizePrompt({
      testRunId: 'run-xyz',
      testRunName: '',
    });

    expect(prompt).toContain('Test run: unnamed');
    expect(prompt).toContain('Endpoint: unknown');
    expect(prompt).toContain('Test set: unknown');
  });
});
