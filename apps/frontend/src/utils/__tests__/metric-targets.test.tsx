import { render } from '@testing-library/react';
import {
  editedTarget,
  formatMetricTarget,
  getMetricTargetIcon,
  targetPhrase,
  isTargetOnValue,
  metricRunsOnTestType,
  offeredTargets,
  toMetricTarget,
} from '../metric-targets';
import type { MetricTargetChoice } from '@/utils/api-client/interfaces/metric';

const CHOICES: MetricTargetChoice[] = [
  { on: 'turn', label: 'Each turn', description: '', per_span: false },
  {
    on: 'conversation',
    label: 'The conversation',
    description: '',
    per_span: false,
  },
  { on: 'tool_call', label: 'Each tool call', description: '', per_span: true },
];

describe('metricRunsOnTestType', () => {
  const conversation = { config: { target: { on: 'conversation' } } };
  const turn = { config: { target: { on: 'turn' } } };

  it('leaves conversation metrics out of single-turn tests', () => {
    expect(metricRunsOnTestType(conversation, 'Single-Turn')).toBe(false);
    expect(metricRunsOnTestType(turn, 'Single-Turn')).toBe(true);
  });

  it('runs every metric on multi-turn tests or when the type is unknown', () => {
    expect(metricRunsOnTestType(conversation, 'Multi-Turn')).toBe(true);
    expect(metricRunsOnTestType(conversation, undefined)).toBe(true);
  });

  it('leaves metrics needing a reference answer out of multi-turn tests', () => {
    const reference = { ...turn, ground_truth_required: true };
    expect(metricRunsOnTestType(reference, 'Multi-Turn')).toBe(false);
    expect(metricRunsOnTestType(reference, 'Single-Turn')).toBe(true);
  });
});

describe('formatMetricTarget', () => {
  it('uses the registry label and adds the name', () => {
    expect(formatMetricTarget({ on: 'turn' }, CHOICES)).toBe('Each turn');
    expect(
      formatMetricTarget({ on: 'tool_call', name: 'search' }, CHOICES)
    ).toBe('Each tool call (search)');
  });

  it('falls back to the raw value before the registry loads', () => {
    expect(formatMetricTarget({ on: 'agent' }, undefined)).toBe('agent');
  });
});

describe('offeredTargets', () => {
  it('narrows to supported targets, keeping registry order', () => {
    expect(
      offeredTargets(CHOICES, { supported: ['tool_call', 'turn'] }).map(
        c => c.on
      )
    ).toEqual(['turn', 'tool_call']);
  });

  it('offers everything when supported targets are unknown', () => {
    expect(offeredTargets(CHOICES, { supported: null })).toHaveLength(3);
  });

  it('drops per-span and conversation targets when a reference answer is required', () => {
    expect(
      offeredTargets(CHOICES, { groundTruthRequired: true }).map(c => c.on)
    ).toEqual(['turn']);
  });
});

describe('toMetricTarget and editedTarget', () => {
  it('sends a trimmed name only for per-span targets', () => {
    expect(
      toMetricTarget({ on: 'tool_call', name: ' search ' }, CHOICES)
    ).toEqual({ on: 'tool_call', name: 'search' });
    expect(toMetricTarget({ on: 'turn', name: 'search' }, CHOICES)).toEqual({
      on: 'turn',
    });
    expect(toMetricTarget({ on: 'tool_call', name: '' }, CHOICES)).toEqual({
      on: 'tool_call',
    });
  });

  it('keeps hidden settings while the target stays the same', () => {
    expect(
      editedTarget(
        { on: 'tool_call', name: 'old', aggregate: 'any' },
        { on: 'tool_call', name: '' },
        CHOICES
      )
    ).toEqual({ on: 'tool_call', aggregate: 'any' });
  });

  it('starts fresh when the target changes', () => {
    expect(
      editedTarget(
        { on: 'turn', aggregate: 'all' },
        { on: 'conversation' },
        CHOICES
      )
    ).toEqual({ on: 'conversation' });
  });
});

describe('isTargetOnValue', () => {
  it('accepts target values and rejects junk', () => {
    expect(isTargetOnValue('tool_call')).toBe(true);
    expect(isTargetOnValue('Three-Turn')).toBe(false);
  });
});

describe('getMetricTargetIcon', () => {
  const kinds = [
    { on: 'turn' },
    { on: 'tool_call', span_kind: 'tool.invoke' },
    { on: 'retrieval', span_kind: 'retrieval' },
  ];
  const iconId = (on: string, choices?: typeof kinds) =>
    render(getMetricTargetIcon(on, choices)).container.querySelector('svg')
      ?.dataset.testid;

  it('gives a per-span target the icon of its span kind', () => {
    expect(iconId('tool_call', kinds)).toBe('BuildIcon');
    expect(iconId('retrieval', kinds)).toBe('SearchIcon');
  });

  it('keeps the turn and conversation icons', () => {
    expect(iconId('turn', kinds)).toBe('ChatBubbleOutlineIcon');
    expect(iconId('conversation', kinds)).toBe('ForumOutlinedIcon');
  });

  it('falls back to one icon for spans when the kinds are not loaded', () => {
    expect(iconId('tool_call')).toBe('AccountTreeOutlinedIcon');
  });
});

describe('targetPhrase', () => {
  it('reads the label as the end of a sentence', () => {
    expect(targetPhrase({ on: 'turn' }, CHOICES)).toBe('each turn');
    expect(targetPhrase({ on: 'conversation' }, CHOICES)).toBe(
      'the conversation'
    );
  });

  it('is null until the labels load', () => {
    expect(targetPhrase({ on: 'turn' }, undefined)).toBeNull();
    expect(targetPhrase({ on: 'unknown' }, CHOICES)).toBeNull();
  });
});
