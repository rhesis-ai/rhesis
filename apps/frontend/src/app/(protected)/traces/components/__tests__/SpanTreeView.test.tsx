import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SpanTreeView from '../SpanTreeView';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

function span(overrides: Partial<SpanNode>): SpanNode {
  return {
    span_id: 'root',
    span_name: 'agent.run',
    span_kind: 'INTERNAL',
    span_type: 'span',
    start_time: '2026-01-01T12:00:00.000Z',
    end_time: '2026-01-01T12:00:01.000Z',
    duration_ms: 1000,
    status_code: 'OK',
    attributes: {},
    events: [],
    children: [],
    ...overrides,
  } as SpanNode;
}

describe('SpanTreeView keyboard access', () => {
  it('selects a span with the keyboard', async () => {
    const user = userEvent.setup();
    const onSpanSelect = jest.fn();
    const child = span({ span_id: 'child', span_name: 'tool.call' });
    const root = span({ children: [child] });

    render(
      <SpanTreeView
        spans={[root]}
        selectedSpan={null}
        onSpanSelect={onSpanSelect}
      />
    );

    const buttons = screen
      .getAllByRole('button', { pressed: false })
      .filter(b => b.textContent?.includes('tool.call'));
    expect(buttons).toHaveLength(1);

    buttons[0].focus();
    await user.keyboard('{Enter}');

    expect(onSpanSelect).toHaveBeenCalledTimes(1);
    expect(onSpanSelect).toHaveBeenCalledWith(child);
  });

  it('marks the selected span as pressed', () => {
    const root = span({});
    render(
      <SpanTreeView
        spans={[root]}
        selectedSpan={root}
        onSpanSelect={jest.fn()}
      />
    );
    expect(screen.getByRole('button', { pressed: true })).toHaveTextContent(
      'agent.run'
    );
  });
});
