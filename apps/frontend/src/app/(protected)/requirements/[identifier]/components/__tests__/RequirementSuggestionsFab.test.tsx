/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import RequirementSuggestionsFab from '../RequirementSuggestionsFab';
import { RULE_HINT_MESSAGES } from '../requirement-suggestions';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('../../../components/requirement-lookups', () => ({
  useRequirementTypes: () => ({ data: [] }),
}));

const base = {
  id: 'req-1',
  name: 'No advice',
  description: 'Respond appropriately.',
  organization_id: 'org-1',
  metrics: [],
  sources: [],
  examples_count: 0,
} as unknown as RequirementWithMetrics;

function renderFab(requirement: RequirementWithMetrics) {
  const onRuleAction = jest.fn();
  render(
    <RequirementSuggestionsFab
      requirement={requirement}
      onUpdated={jest.fn()}
      onRuleAction={onRuleAction}
    />
  );
  return { onRuleAction };
}

describe('RequirementSuggestionsFab', () => {
  it('counts open suggestions in the badge', () => {
    renderFab({
      ...base,
      review: {
        reviewed_at: '2026-10-20T10:00:00Z',
        description_hash: 'x',
        hints: [
          {
            kind: 'vague_wording',
            message: '“appropriately” is vague.',
            quote: 'appropriately',
            suggestion: null,
          },
        ],
      },
    } as any);
    // Three rule hints plus one AI hint.
    expect(
      screen.getByRole('button', { name: 'Suggestions (4 open)' })
    ).toBeInTheDocument();
  });

  it('shows no count when there is nothing to fix', () => {
    renderFab({
      ...base,
      sources: [{ id: 's1', title: 'Policy' }],
      examples_count: 1,
      metrics: [{ id: 'm1' }],
    } as any);
    expect(
      screen.getByRole('button', { name: 'Suggestions' })
    ).toBeInTheDocument();
  });

  it('lists the hints in the drawer and runs a rule action', async () => {
    const { onRuleAction } = renderFab(base);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Suggestions/ }));

    expect(
      await screen.findByText(RULE_HINT_MESSAGES.no_source)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Link metric' }));
    expect(onRuleAction).toHaveBeenCalledWith('no_metric');
  });
});
