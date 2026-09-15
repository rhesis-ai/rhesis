import React from 'react';
import { render, screen, fireEvent, waitFor } from '@/test-utils';
import '@testing-library/jest-dom';
import TestRunAnnotationsTab from '../TestRunAnnotationsTab';
import type { Annotation } from '@/utils/api-client/interfaces/annotation';

const getAnnotations = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getAnnotationsClient: () => ({ getAnnotations }),
  })),
}));

jest.mock('@/hooks/useIsAuthenticated', () => ({
  useIsAuthenticated: () => true,
}));

function annotation(
  id: string,
  name: string,
  updatedAt: string,
  overrides: Partial<Annotation> = {}
): Annotation {
  return {
    id,
    entity_type: 'TestResult',
    entity_id: `result-${id}`,
    target_type: 'test_result',
    target_reference: null,
    status_id: 'status-1',
    status: { name: 'Pass' },
    user_id: `user-${name}`,
    user: { name },
    comments: '',
    resolved: false,
    created_at: updatedAt,
    updated_at: updatedAt,
    ...overrides,
  } as unknown as Annotation;
}

function resolvesTo(rows: Annotation[]) {
  getAnnotations.mockResolvedValue({ data: rows, totalCount: rows.length });
}

describe('TestRunAnnotationsTab', () => {
  beforeEach(() => {
    getAnnotations.mockReset();
  });

  it('shows the empty state when nothing in the run is annotated', async () => {
    resolvesTo([]);
    render(<TestRunAnnotationsTab testRunId="run1" />);

    expect(await screen.findByText('No annotations yet')).toBeInTheDocument();
  });

  it('scopes the query to the run rather than to loaded results', async () => {
    resolvesTo([]);
    render(<TestRunAnnotationsTab testRunId="run1" />);

    await waitFor(() => expect(getAnnotations).toHaveBeenCalled());
    expect(getAnnotations).toHaveBeenCalledWith(
      expect.objectContaining({ test_run_id: 'run1', sort_order: 'desc' })
    );
  });

  it('lists annotations from across the run', async () => {
    resolvesTo([
      annotation('r1', 'Alice', '2026-09-01T10:00:00Z'),
      annotation('r2', 'Bob', '2026-09-02T10:00:00Z'),
    ]);
    render(<TestRunAnnotationsTab testRunId="run1" />);

    expect(await screen.findByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('hands back the result id so the caller can open it in place', async () => {
    // The caller opens a drawer without leaving the tab.
    const onViewTestResult = jest.fn();
    resolvesTo([annotation('r1', 'Alice', '2026-09-01T10:00:00Z')]);
    render(
      <TestRunAnnotationsTab
        testRunId="run1"
        onViewTestResult={onViewTestResult}
      />
    );

    fireEvent.click(await screen.findByText('Alice'));

    expect(onViewTestResult).toHaveBeenCalledWith('result-r1');
  });

  it('does not blow up when no handler is given', async () => {
    resolvesTo([annotation('r1', 'Alice', '2026-09-01T10:00:00Z')]);
    render(<TestRunAnnotationsTab testRunId="run1" />);

    fireEvent.click(await screen.findByText('Alice'));

    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('shows the comment and its verdict', async () => {
    resolvesTo([
      annotation('r1', 'Alice', '2026-09-01T10:00:00Z', {
        status: { name: 'Fail' },
        comments: 'Wrong refusal',
      }),
    ]);
    render(<TestRunAnnotationsTab testRunId="run1" />);

    expect(await screen.findByText('Wrong refusal')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
});
