/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import AnnotationDrawer from '../AnnotationDrawer';
import { ANNOTATION_COPY } from '../annotation-copy';
import type { Annotation } from '@/utils/api-client/interfaces/annotation';

const mockCreate = jest.fn();
const mockUpdate = jest.fn();
const mockAddAsTuningCase = jest.fn();
const mockGetRequirementWithMetrics = jest.fn();

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

jest.mock('@/hooks/useAnnotations', () => ({
  useAnnotationMutations: () => ({ create: mockCreate, update: mockUpdate }),
}));

jest.mock('@/components/common/MentionTextInput', () => ({
  __esModule: true,
  default: ({
    value,
    onChange,
    label,
  }: {
    value: string;
    onChange: (v: string) => void;
    label: string;
  }) => (
    <textarea
      aria-label={label}
      value={value}
      onChange={e => onChange(e.target.value)}
    />
  ),
  inferAnnotationTarget: (_comment: string, fallback: string) => ({
    type: fallback,
  }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getStatusClient: () => ({
      getStatuses: jest.fn().mockResolvedValue([
        { id: 'pass-id', name: 'Pass' },
        { id: 'fail-id', name: 'Fail' },
      ]),
    }),
    getRequirementClient: () => ({
      getRequirementWithMetrics: mockGetRequirementWithMetrics,
      getRequirements: jest.fn().mockResolvedValue([]),
    }),
    getAnnotationsClient: () => ({
      addAsTuningCase: mockAddAsTuningCase,
    }),
  })),
}));

const REQUIREMENT = { id: 'req-1', name: 'No investment advice' } as any;

function renderDrawer(
  props: Partial<React.ComponentProps<typeof AnnotationDrawer>> = {}
) {
  return render(
    <AnnotationDrawer
      open
      onClose={jest.fn()}
      entityType="TestResult"
      entityId="result-1"
      onSaved={jest.fn()}
      {...props}
    />
  );
}

async function fillVerdictAndComment() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: /fail/i }));
  await user.type(
    screen.getByLabelText('Comment'),
    'Recommends a specific fund.'
  );
  return user;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockCreate.mockResolvedValue({ id: 'ann-1' });
  mockUpdate.mockResolvedValue({ id: 'ann-1' });
  mockAddAsTuningCase.mockResolvedValue({
    metric_id: 'm-custom',
    case_id: 'c1',
  });
  mockGetRequirementWithMetrics.mockResolvedValue({
    id: 'req-1',
    name: 'No investment advice',
    metrics: [
      {
        id: 'm-custom',
        name: 'Advice judge',
        backend_type: { type_value: 'custom' },
      },
      {
        id: 'm-rhesis',
        name: 'Answer relevancy',
        backend_type: { type_value: 'rhesis' },
      },
    ],
  });
});

const improveBox = () =>
  screen.getByRole('checkbox', { name: ANNOTATION_COPY.improveLabel });

describe('AnnotationDrawer "improve the evaluation"', () => {
  it('names the requirement and its tunable metrics instead of asking for them', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT });
    const user = userEvent.setup();

    expect(improveBox()).not.toBeChecked();
    await user.click(improveBox());

    // Only the custom metric can take a tuning case.
    expect(
      await screen.findByText(
        ANNOTATION_COPY.improveSummary('No investment advice', [
          'Advice judge',
        ]),
        { exact: false }
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('combobox', { name: ANNOTATION_COPY.requirementLabel })
    ).not.toBeInTheDocument();
  });

  it('starts checked when the verdict disagrees with the automated one', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT, automatedPassed: true });
    await fillVerdictAndComment(); // picks Fail

    expect(improveBox()).toBeChecked();
  });

  it('stays unchecked when the verdict agrees with the automated one', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT, automatedPassed: false });
    await fillVerdictAndComment(); // picks Fail

    expect(improveBox()).not.toBeChecked();
  });

  it('links the requirement and adds a tuning case for each tunable metric', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT, automatedPassed: true });
    const user = await fillVerdictAndComment();
    await screen.findByText(/used to check Advice judge/);
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ statusId: 'fail-id', requirementId: 'req-1' })
      )
    );
    expect(mockAddAsTuningCase).toHaveBeenCalledWith('ann-1', 'm-custom');
    expect(mockAddAsTuningCase).toHaveBeenCalledTimes(1);
  });

  it('saves a plain annotation when unchecked', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT });
    const user = await fillVerdictAndComment();
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ requirementId: null })
      )
    );
    expect(mockAddAsTuningCase).not.toHaveBeenCalled();
  });

  it('shows the requirement picker on "Change", and when there is none', async () => {
    const user = userEvent.setup();
    const { unmount } = renderDrawer({ initialRequirement: REQUIREMENT });
    await user.click(improveBox());
    await user.click(
      await screen.findByRole('button', { name: ANNOTATION_COPY.improveChange })
    );
    expect(improveBox()).toBeChecked();
    expect(
      screen.getByRole('combobox', { name: ANNOTATION_COPY.requirementLabel })
    ).toHaveValue('No investment advice');
    unmount();

    renderDrawer();
    await user.click(improveBox());
    expect(
      screen.getByRole('combobox', { name: ANNOTATION_COPY.requirementLabel })
    ).toBeInTheDocument();
  });

  it('keeps an edit that did not change the link as it was, without new cases', async () => {
    const annotation = {
      id: 'ann-1',
      status_id: 'pass-id',
      comments: 'Already a long enough comment',
      resolved: false,
      requirement_id: 'req-1',
    } as unknown as Annotation;
    renderDrawer({ annotation });

    expect(improveBox()).toBeChecked();
    await screen.findByText(/No investment advice/);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    expect(mockUpdate.mock.calls[0][1]).not.toHaveProperty('requirement_id');
    expect(mockAddAsTuningCase).not.toHaveBeenCalled();
  });

  it('unlinks the requirement when an edit unticks it', async () => {
    const annotation = {
      id: 'ann-1',
      status_id: 'pass-id',
      comments: 'Already a long enough comment',
      resolved: false,
      requirement_id: 'req-1',
    } as unknown as Annotation;
    renderDrawer({ annotation });
    const user = userEvent.setup();

    await user.click(improveBox());
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    expect(mockUpdate.mock.calls[0][1]).toHaveProperty('requirement_id', null);
  });
});
