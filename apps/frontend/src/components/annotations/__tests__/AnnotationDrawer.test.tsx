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

describe('AnnotationDrawer requirement field', () => {
  it('prefills the requirement and offers tuning only for custom metrics, unchecked', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT });

    expect(
      screen.getByRole('combobox', { name: ANNOTATION_COPY.requirementLabel })
    ).toHaveValue('No investment advice');
    expect(
      screen.getByText(ANNOTATION_COPY.requirementHelp)
    ).toBeInTheDocument();

    const box = await screen.findByRole('checkbox', {
      name: ANNOTATION_COPY.tuningCaseLabel('Advice judge'),
    });
    expect(box).not.toBeChecked();
    expect(
      screen.queryByRole('checkbox', {
        name: ANNOTATION_COPY.tuningCaseLabel('Answer relevancy'),
      })
    ).not.toBeInTheDocument();
  });

  it('sends the requirement and adds a tuning case for each checked metric', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT });
    const user = await fillVerdictAndComment();
    await user.click(
      await screen.findByRole('checkbox', {
        name: ANNOTATION_COPY.tuningCaseLabel('Advice judge'),
      })
    );
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ statusId: 'fail-id', requirementId: 'req-1' })
      )
    );
    expect(mockAddAsTuningCase).toHaveBeenCalledWith('ann-1', 'm-custom');
    expect(mockAddAsTuningCase).toHaveBeenCalledTimes(1);
  });

  it('adds no tuning case when nothing is checked', async () => {
    renderDrawer({ initialRequirement: REQUIREMENT });
    const user = await fillVerdictAndComment();
    await screen.findByRole('checkbox', {
      name: ANNOTATION_COPY.tuningCaseLabel('Advice judge'),
    });
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalled());
    expect(mockAddAsTuningCase).not.toHaveBeenCalled();
  });

  it('creates a plain annotation without a requirement', async () => {
    renderDrawer();
    const user = await fillVerdictAndComment();
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ requirementId: null })
      )
    );
    expect(mockGetRequirementWithMetrics).not.toHaveBeenCalled();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('leaves the requirement out of an edit that did not change it', async () => {
    const annotation = {
      id: 'ann-1',
      status_id: 'pass-id',
      comments: 'Already a long enough comment',
      resolved: false,
      requirement_id: 'req-1',
    } as unknown as Annotation;
    renderDrawer({ annotation });

    await waitFor(() =>
      expect(
        screen.getByRole('combobox', { name: ANNOTATION_COPY.requirementLabel })
      ).toHaveValue('No investment advice')
    );
    await userEvent.setup().click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    expect(mockUpdate.mock.calls[0][1]).not.toHaveProperty('requirement_id');
  });
});
