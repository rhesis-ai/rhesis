import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import TestRunConfigurationTab from '../TestRunConfigurationTab';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

function testRun(
  runAttributes: Record<string, unknown>,
  configAttributes: Record<string, unknown>
): TestRunDetail {
  return {
    id: 'run-1',
    attributes: runAttributes,
    test_configuration: {
      attributes: configAttributes,
      endpoint: { id: 'ep-1', name: 'Digitaler Assistent' },
      test_set: { id: 'ts-1', name: 'Bürgeranfragen' },
    },
  } as unknown as TestRunDetail;
}

describe('TestRunConfigurationTab configuration source', () => {
  it('prefers the snapshot frozen onto the run', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun(
          { run_config: { execution_mode: 'Sequential' } },
          { execution_mode: 'Parallel' }
        )}
      />
    );

    expect(screen.getByText('Sequential')).toBeInTheDocument();
  });

  it('ignores a configuration edited after the run finished', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun(
          { run_config: { execution_mode: 'Sequential' } },
          { execution_mode: 'Parallel', metrics_source: 'test_set' }
        )}
      />
    );

    expect(screen.queryByText('Parallel')).not.toBeInTheDocument();
  });

  it.each([
    ['a string', 'nonsense'],
    ['an array', ['nonsense']],
    ['a number', 42],
  ])(
    'falls back to the live configuration when run_config is %s',
    (_label, value) => {
      render(
        <TestRunConfigurationTab
          testRun={testRun(
            { run_config: value },
            { execution_mode: 'Parallel' }
          )}
        />
      );

      // Without the guard this would win the ?? and render an empty configuration.
      expect(screen.getByText('Parallel')).toBeInTheDocument();
    }
  );

  it('falls back to the live configuration for runs predating the snapshot', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun({}, { execution_mode: 'Parallel' })}
      />
    );

    expect(screen.getByText('Parallel')).toBeInTheDocument();
  });
});

describe('TestRunConfigurationTab preflight checks', () => {
  it('reports preflight as off when the run recorded it off', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun({ run_config: { run_preflight_checks: false } }, {})}
      />
    );

    expect(screen.getByRole('switch')).not.toBeChecked();
  });

  it('reports preflight as on when the run recorded it on', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun({ run_config: { run_preflight_checks: true } }, {})}
      />
    );

    expect(screen.getByRole('switch')).toBeChecked();
  });
});

describe('TestRunConfigurationTab evaluation model', () => {
  it('names the model the run actually resolved', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun(
          {
            run_config: {
              evaluation_model_name: 'gpt-4o',
              evaluation_model_id: '8f3e1c22-0000-4000-8000-000000000000',
            },
          },
          {}
        )}
      />
    );

    expect(screen.getByText('gpt-4o')).toBeInTheDocument();
  });

  it('never shows a bare model id when a name is present', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun(
          {
            run_config: {
              evaluation_model_name: 'gpt-4o',
              evaluation_model_id: '8f3e1c22-0000-4000-8000-000000000000',
            },
          },
          {}
        )}
      />
    );

    expect(
      screen.queryByText('8f3e1c22-0000-4000-8000-000000000000')
    ).not.toBeInTheDocument();
  });
});

describe('TestRunConfigurationTab version information', () => {
  it('renders the recorded version from the run snapshot', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun(
          {
            version_info: { prompt_version: 'v3.2' },
            version_info_source: 'endpoint',
          },
          {}
        )}
      />
    );

    expect(screen.getByText('Version Information')).toBeInTheDocument();
    expect(screen.getByText(/prompt_version/)).toBeInTheDocument();
    expect(screen.getByText(/v3\.2/)).toBeInTheDocument();
  });

  it('says where the version came from', () => {
    render(
      <TestRunConfigurationTab
        testRun={testRun(
          {
            version_info: { prompt_version: 'v3.2' },
            version_info_source: 'response',
          },
          {}
        )}
      />
    );

    expect(screen.getByText(/Reported by the endpoint/i)).toBeInTheDocument();
  });

  it('shows an empty state when the run recorded no version', () => {
    render(<TestRunConfigurationTab testRun={testRun({}, {})} />);

    expect(
      screen.getByText('No version information recorded')
    ).toBeInTheDocument();
  });

  it('ignores the endpoint\u2019s current value, which may have changed since the run', () => {
    const run = testRun({}, {});
    // Endpoint edited after the run finished; the run itself recorded nothing.
    (
      run.test_configuration as unknown as {
        endpoint: Record<string, unknown>;
      }
    ).endpoint.version_info = { prompt_version: 'v9-edited-later' };

    render(<TestRunConfigurationTab testRun={run} />);

    expect(screen.queryByText(/v9-edited-later/)).not.toBeInTheDocument();
    expect(
      screen.getByText('No version information recorded')
    ).toBeInTheDocument();
  });
});
