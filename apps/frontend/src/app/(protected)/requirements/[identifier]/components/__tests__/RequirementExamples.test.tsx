/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import RequirementExamples, {
  EXAMPLES_EMPTY_TEXT,
} from '../RequirementExamples';
import type {
  RequirementExample,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';

const mockAddAsTuningCase = jest.fn();

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: {} }, status: 'authenticated' }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getRequirementClient: () => ({ getExamples: jest.fn() }),
    getAnnotationsClient: () => ({ addAsTuningCase: mockAddAsTuningCase }),
  })),
}));

const requirement = {
  id: 'req-1',
  name: 'No investment advice',
  organization_id: 'org-1',
  metrics: [
    {
      id: 'm-custom',
      name: 'Advice judge',
      backend_type: { type_value: 'custom' },
    },
    {
      id: 'm-rhesis',
      name: 'Relevancy',
      backend_type: { type_value: 'rhesis' },
    },
  ],
} as unknown as RequirementWithMetrics;

function example(
  overrides: Partial<RequirementExample> = {}
): RequirementExample {
  return {
    annotation: {
      id: 'ann-1',
      entity_type: 'TestResult',
      entity_id: 'tr-1',
      target_type: 'test_result',
      status_id: 's',
      status: { name: 'Fail' },
      user_id: 'u',
      user: { name: 'Maria Keller' },
      comments: 'Names a product for this customer.',
      resolved: false,
      created_at: '2026-10-20T10:00:00Z',
      updated_at: '2026-10-20T10:00:00Z',
      context: { test_run_id: 'run-1', test_run_name: 'Run 418' },
    } as any,
    input: 'Should I buy the MSCI World ETF?',
    output: 'Yes, it is a great fit for you.',
    tuning_cases: [],
    ...overrides,
  };
}

function renderExamples(examples: RequirementExample[]) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <RequirementExamples
        requirement={requirement}
        initialExamples={examples}
      />
    </ThemeProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockAddAsTuningCase.mockResolvedValue({
    metric_id: 'm-custom',
    case_id: 'c-1',
  });
});

describe('RequirementExamples', () => {
  it('explains how to add an example when there are none', () => {
    renderExamples([]);
    expect(screen.getByText('No examples yet')).toBeInTheDocument();
    expect(screen.getByText(EXAMPLES_EMPTY_TEXT)).toBeInTheDocument();
  });

  it('shows the exchange, verdict, comment and where it came from', () => {
    renderExamples([example()]);
    expect(
      screen.getByText('Should I buy the MSCI World ETF?')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Yes, it is a great fit for you.')
    ).toBeInTheDocument();
    expect(screen.getByText('Fail')).toBeInTheDocument();
    expect(
      screen.getByText('Names a product for this customer.')
    ).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Test Result · Run 418' });
    expect(link).toHaveAttribute(
      'href',
      '/test-runs/run-1?selectedresult=tr-1&detailTab=annotations'
    );
    expect(screen.getByText(/Maria Keller/)).toBeInTheDocument();
  });

  it('links existing tuning cases to the metric tuning tab', () => {
    renderExamples([
      example({
        tuning_cases: [{ metric_id: 'm-custom', case_id: 'c-1' } as any],
      }),
    ]);
    expect(screen.getByRole('link', { name: 'Advice judge' })).toHaveAttribute(
      'href',
      '/metrics/m-custom?tab=tuning'
    );
    expect(
      screen.queryByRole('button', { name: 'Add as tuning case' })
    ).not.toBeInTheDocument();
  });

  it('adds a tuning case for each custom linked metric', async () => {
    renderExamples([example()]);
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Add as tuning case' }));

    await waitFor(() =>
      expect(mockAddAsTuningCase).toHaveBeenCalledWith('ann-1', 'm-custom')
    );
    expect(mockAddAsTuningCase).toHaveBeenCalledTimes(1);
    const grid = screen.getByRole('grid');
    expect(
      await within(grid).findByRole('link', { name: 'Advice judge' })
    ).toBeInTheDocument();
  });
});
