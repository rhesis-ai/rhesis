import React from 'react';
import { render, screen, fireEvent, within } from '@/test-utils';
import '@testing-library/jest-dom';

import MetricTargetBuilder from '../MetricTargetBuilder';
import { draftFromTarget, type TargetDraft } from '@/utils/metric-target-draft';
import type {
  MetricTarget,
  MetricTargetChoice,
  MetricTargetPreview,
} from '@/utils/api-client/interfaces/metric';
import type { SpanAttributeCatalogue } from '@/utils/api-client/interfaces/telemetry';

const mockChoices: MetricTargetChoice[] = [
  {
    on: 'turn',
    label: 'Each turn',
    description: 'Each exchange.',
    per_span: false,
  },
  {
    on: 'run',
    label: 'The whole run',
    description: 'The trace.',
    per_span: false,
  },
  {
    on: 'tool_call',
    label: 'Each tool call',
    description: 'Every tool call.',
    per_span: true,
    span_kind: 'tool.invoke',
  },
];

jest.mock('@/hooks/useLookups', () => ({
  useMetricTargetOptions: () => ({
    data: {
      targets: mockChoices,
      operators: [
        { op: '==', takes_value: true, value_type: 'text' },
        { op: '<', takes_value: true, value_type: 'number' },
        { op: 'in', takes_value: true, value_type: 'list' },
        { op: 'matches', takes_value: true, value_type: 'pattern' },
        { op: 'exists', takes_value: false, value_type: 'none' },
      ],
      special_fields: [
        { field: 'kind', label: 'Kind' },
        { field: 'duration_ms', label: 'Duration (ms)' },
      ],
      readers: [
        { reader: 'input', label: 'Its own input' },
        { reader: 'conversation.output', label: "The turn's output" },
      ],
      event_prefix: 'event:',
    },
  }),
}));

const mockCatalogue: SpanAttributeCatalogue = {
  sampled_spans: 10,
  since: '2026-11-20T00:00:00Z',
  kinds: {
    'tool.invoke': {
      spans: 10,
      attributes: [
        {
          key: 'app.customer_tier',
          coverage: 0.92,
          type: 'string',
          top_values: [
            { value: 'gold', count: 6, truncated: false },
            { value: 'a long cut valu…', count: 2, truncated: true },
          ],
          distinct: 3,
          unique: false,
        },
        {
          key: 'ai.tool.call.id',
          coverage: 1,
          type: 'string',
          top_values: [],
          distinct: 10,
          unique: true,
        },
      ],
    },
  },
};

let mockPreviewResult: {
  data?: MetricTargetPreview;
  pending: boolean;
  isFetching: boolean;
  isLoading: boolean;
  isPlaceholderData: boolean;
  error: Error | null;
};
const mockPreviewArgs = jest.fn();
jest.mock('@/hooks/useMetricTargetBuilder', () => ({
  TARGET_PREVIEW_TRACES: 50,
  useSpanAttributeCatalogue: () => ({ data: mockCatalogue }),
  useMetricTargetPreview: (projectId: string, target: unknown) => {
    mockPreviewArgs(projectId, target);
    return mockPreviewResult;
  },
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ activeProject: { id: 'project-1' } }),
}));

const mockAnnounce = jest.fn();
jest.mock('@/components/common/LiveAnnouncer', () => ({
  useAnnounce: () => mockAnnounce,
}));

const PREVIEW: MetricTargetPreview = {
  traces: 50,
  matching_traces: 27,
  units: 38,
  not_applicable_traces: 23,
  samples: [
    {
      trace_id: 't1',
      span_id: 's1',
      name: 'issue_refund',
      input: '{"order_id": "ORD-1"}',
      output: '{"status": "refunded"}',
      duration_ms: 412,
      status: 'ok',
    },
  ],
  target_summary: 'each tool call named `issue_refund`',
};

function settled(data?: MetricTargetPreview) {
  mockPreviewResult = {
    data,
    pending: false,
    isFetching: false,
    isLoading: false,
    isPlaceholderData: false,
    error: null,
  };
}

/** The builder with its own state, as the section and the form hold it. */
function Harness({
  initial,
  saved,
  savedSummary,
}: {
  initial: MetricTarget | null;
  saved?: MetricTarget | null;
  savedSummary?: string | null;
}) {
  const [draft, setDraft] = React.useState<TargetDraft>(() =>
    draftFromTarget(initial, 'turn')
  );
  return (
    <MetricTargetBuilder
      choices={[
        ...mockChoices,
        {
          on: 'span',
          label: 'Custom spans',
          description: 'Spans by conditions.',
          per_span: true,
        },
      ]}
      value={draft}
      onChange={setDraft}
      savedTarget={saved}
      savedSummary={savedSummary}
    />
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  settled(PREVIEW);
});

describe('MetricTargetBuilder', () => {
  it('offers the presets and custom spans as one radio group', () => {
    render(<Harness initial={{ on: 'turn' }} />);
    const group = screen.getByRole('radiogroup', { name: 'Start from' });
    expect(
      within(group)
        .getAllByRole('radio')
        .map(r => r.textContent)
    ).toEqual(['Each turn', 'The whole run', 'Each tool call', 'Custom spans']);
    expect(
      within(group).getByRole('radio', { name: 'Each turn' })
    ).toHaveAttribute('aria-checked', 'true');
  });

  it('shows the saved summary while the draft is the stored target', () => {
    settled(undefined);
    render(
      <Harness
        initial={{ on: 'turn' }}
        saved={{ on: 'turn' }}
        savedSummary="each turn"
      />
    );
    expect(screen.getByTestId('target-summary')).toHaveTextContent(
      'Judges each turn.'
    );
  });

  it("shows the preview's summary for an edited draft", () => {
    render(
      <Harness
        initial={{ on: 'tool_call', name: 'issue_refund' }}
        saved={{ on: 'turn' }}
        savedSummary="each turn"
      />
    );
    const summary = screen.getByTestId('target-summary');
    expect(summary).toHaveTextContent(
      'Judges each tool call named issue_refund.'
    );
    expect(summary.querySelector('code')).toHaveTextContent('issue_refund');
  });

  it('previews only a complete draft', () => {
    render(<Harness initial={{ on: 'turn' }} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Custom spans' }));
    // The new empty condition row makes the draft incomplete.
    expect(mockPreviewArgs).toHaveBeenLastCalledWith('project-1', null);
    expect(screen.getByTestId('target-preview')).toHaveTextContent(
      'The preview runs once the target is complete.'
    );
  });

  it('asks a per-span preset for a name and an agent, and custom spans only for an agent', () => {
    render(<Harness initial={{ on: 'tool_call' }} />);
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Inside agent')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('radio', { name: 'Custom spans' }));
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Inside agent')).toBeInTheDocument();
  });

  it('starts custom spans from the preset kind it came from', () => {
    render(<Harness initial={{ on: 'tool_call' }} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Custom spans' }));
    expect(mockPreviewArgs).toHaveBeenLastCalledWith('project-1', {
      on: 'span',
      where: [{ field: 'kind', op: '==', value: 'tool.invoke' }],
    });
  });

  it('offers read and the pass rule only for targets with several units', () => {
    const { unmount } = render(<Harness initial={{ on: 'run' }} />);
    expect(
      screen.queryByLabelText('The metric reads as input')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('group', { name: 'Pass rule' })
    ).not.toBeInTheDocument();
    unmount();

    render(<Harness initial={{ on: 'tool_call' }} />);
    expect(
      screen.getByLabelText('The metric reads as input')
    ).toBeInTheDocument();
    expect(screen.getByLabelText('And as output')).toBeInTheDocument();
    expect(
      screen.getByRole('group', { name: 'Pass rule' })
    ).toBeInTheDocument();
  });

  it('sends read and a share pass rule', () => {
    render(
      <Harness
        initial={{ on: 'tool_call', aggregate: 'share', min_share: 0.9 }}
      />
    );
    expect(
      screen.getByLabelText('Share that must pass, in percent')
    ).toHaveValue('90');
    fireEvent.change(screen.getByLabelText('The metric reads as input'), {
      target: { value: 'ai.tool.arguments' },
    });
    expect(mockPreviewArgs).toHaveBeenLastCalledWith('project-1', {
      on: 'tool_call',
      read: { input: 'ai.tool.arguments' },
      aggregate: 'share',
      min_share: 0.9,
    });
  });

  it("offers the API's readers, then the kind's keys, for read", () => {
    render(<Harness initial={{ on: 'tool_call' }} />);
    const input = screen.getByLabelText('The metric reads as input');
    fireEvent.mouseDown(input);
    fireEvent.keyDown(input, { key: 'ArrowDown' });

    const options = within(screen.getByRole('listbox'))
      .getAllByRole('option')
      .map(o => o.textContent);
    expect(options).toEqual([
      'inputIts own input',
      "conversation.outputThe turn's output",
      'ai.tool.call.id',
      'app.customer_tier',
    ]);
    expect(
      screen.getByText(/or event:<name> for an event/)
    ).toBeInTheDocument();
  });

  it('adds and removes condition rows by name', () => {
    render(<Harness initial={{ on: 'tool_call' }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add condition' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add condition' }));
    expect(screen.getAllByTestId('target-condition-row')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Remove condition 1' }));
    expect(screen.getAllByTestId('target-condition-row')).toHaveLength(1);
  });
});

describe('MetricTargetBuilder preview', () => {
  it('shows the counts and the samples, and announces them politely once', () => {
    const { rerender } = render(<Harness initial={{ on: 'tool_call' }} />);
    const panel = screen.getByTestId('target-preview');
    expect(panel).toHaveTextContent('38spans in 27 traces');
    expect(panel).toHaveTextContent('23traces not applicable');
    expect(
      within(panel).getByRole('list', { name: 'Examples' })
    ).toHaveTextContent('issue_refund');
    expect(mockAnnounce).toHaveBeenCalledWith(
      'Preview: 38 spans in 27 traces; 23 traces not applicable.'
    );
    rerender(<Harness initial={{ on: 'tool_call' }} />);
    expect(mockAnnounce).toHaveBeenCalledTimes(1);
  });

  it('says when there are no traces yet', () => {
    settled({
      ...PREVIEW,
      traces: 0,
      matching_traces: 0,
      units: 0,
      not_applicable_traces: 0,
      samples: [],
    });
    render(<Harness initial={{ on: 'tool_call' }} />);
    expect(screen.getByTestId('target-preview-no-traces')).toHaveTextContent(
      'No traces yet'
    );
  });

  it('says what the endpoint must report when nothing matches', () => {
    settled({
      ...PREVIEW,
      matching_traces: 0,
      units: 0,
      not_applicable_traces: 50,
      samples: [],
    });
    render(<Harness initial={{ on: 'tool_call', name: 'issue_refund' }} />);
    expect(screen.getByTestId('target-preview-no-match')).toHaveTextContent(
      'Nothing matches in the last 50 traces' +
        'Every one would be not applicable. For this metric to run, the endpoint must report each tool call named issue_refund in its traces.'
    );
  });

  it("shows the API's refusal of a bad target", () => {
    mockPreviewResult = {
      ...mockPreviewResult,
      data: undefined,
      error: new Error('API error: 422 - Invalid target: bad pattern'),
    };
    render(<Harness initial={{ on: 'tool_call' }} />);
    expect(screen.getByTestId('target-preview-error')).toHaveTextContent(
      'Invalid target: bad pattern'
    );
  });
});

describe('MetricTargetBuilder conditions', () => {
  function row() {
    return screen.getByRole('group', { name: 'Condition 1' });
  }

  it('lists special fields and catalogue keys by kind, without unique keys', () => {
    render(<Harness initial={{ on: 'tool_call' }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add condition' }));
    const field = within(row()).getByLabelText('Field');
    fireEvent.mouseDown(field);
    fireEvent.keyDown(field, { key: 'ArrowDown' });

    const listbox = screen.getByRole('listbox');
    expect(listbox).toHaveTextContent('Any span');
    expect(listbox).toHaveTextContent('Duration (ms)');
    expect(listbox).toHaveTextContent('Each tool call (tool.invoke)');
    expect(listbox).toHaveTextContent('app.customer_tier');
    expect(listbox).toHaveTextContent('on 92%: gold');
    expect(listbox).not.toHaveTextContent('ai.tool.call.id');
  });

  it('takes operators from the API and fits the value input to them', () => {
    render(<Harness initial={{ on: 'tool_call' }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add condition' }));

    fireEvent.mouseDown(within(row()).getByLabelText('Operator'));
    const options = within(screen.getByRole('listbox'))
      .getAllByRole('option')
      .map(o => o.textContent);
    expect(options).toEqual([
      'is',
      'is under',
      'is any of',
      'matches pattern',
      'is set',
    ]);
    fireEvent.click(screen.getByRole('option', { name: 'is under' }));
    expect(within(row()).getByLabelText('Number')).toBeInTheDocument();

    fireEvent.mouseDown(within(row()).getByLabelText('Operator'));
    fireEvent.click(screen.getByRole('option', { name: 'is set' }));
    expect(
      within(row()).queryByLabelText(/Value|Number/)
    ).not.toBeInTheDocument();
  });

  it('suggests top values but never a truncated one', () => {
    render(
      <Harness
        initial={{
          on: 'tool_call',
          where: [{ field: 'app.customer_tier', op: '==', value: 'g' }],
        }}
      />
    );
    const value = within(row()).getByLabelText('Value');
    fireEvent.change(value, { target: { value: '' } });
    fireEvent.mouseDown(value);
    fireEvent.keyDown(value, { key: 'ArrowDown' });

    const options = within(screen.getByRole('listbox'))
      .getAllByRole('option')
      .map(o => o.textContent);
    expect(options).toEqual(['gold']);
  });
});
