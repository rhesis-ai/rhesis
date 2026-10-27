import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ToolCallList from '../ToolCallList';
import { StreamingState } from '@/hooks/useArchitectChat';

type CompletedTool = StreamingState['completedTools'][number];
type ActiveTool = StreamingState['activeTools'][number];

function makeDone(
  n: number,
  overrides: Partial<CompletedTool> = {}
): CompletedTool[] {
  return Array.from({ length: n }, (_, i) => ({
    tool: `tool_${i}`,
    description: `Tool ${i} done`,
    success: true,
    reasoning: `Reasoning for tool ${i}`,
    startedAt: 1000 + i,
    ...overrides,
  }));
}

describe('ToolCallList', () => {
  it('returns null when there are no tools', () => {
    const { container } = render(
      <ToolCallList completedTools={[]} activeTools={[]} />
    );

    expect(container.firstChild).toBeNull();
  });

  it('shows all completed tools when count <= 2', () => {
    const tools = makeDone(2);
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    expect(screen.getByText('Tool 0 done')).toBeInTheDocument();
    expect(screen.getByText('Tool 1 done')).toBeInTheDocument();
    expect(screen.queryByText(/completed/)).not.toBeInTheDocument();
  });

  it('collapses older tools when count > 2', () => {
    const tools = makeDone(5);
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    expect(screen.getByText('3 completed')).toBeInTheDocument();
    expect(screen.getByText('Tool 3 done')).toBeInTheDocument();
    expect(screen.getByText('Tool 4 done')).toBeInTheDocument();
    expect(screen.queryByText('Tool 0 done')).not.toBeVisible();
  });

  it('expands collapsed tools on click', () => {
    const tools = makeDone(4);
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    fireEvent.click(screen.getByText('2 completed'));

    expect(screen.getByText('Tool 0 done')).toBeVisible();
    expect(screen.getByText('Tool 1 done')).toBeVisible();
  });

  it('hides reasoning for completed tools by default', () => {
    const tools = makeDone(1);
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    expect(screen.getByText('Tool 0 done')).toBeInTheDocument();
    expect(screen.queryByText('Reasoning for tool 0')).not.toBeVisible();
  });

  it('shows reasoning for completed tool on click', () => {
    const tools = makeDone(1);
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    fireEvent.click(screen.getByText('Tool 0 done'));

    expect(screen.getByText('Reasoning for tool 0')).toBeVisible();
  });

  it('always shows active tool reasoning', () => {
    const active: ActiveTool[] = [
      {
        tool: 'explore',
        description: 'Exploring endpoint',
        reasoning: 'Need to check capabilities',
        startedAt: 1000,
      },
    ];
    render(<ToolCallList completedTools={[]} activeTools={active} />);

    expect(screen.getByText('Exploring endpoint')).toBeInTheDocument();
    expect(screen.getByText('Need to check capabilities')).toBeVisible();
  });

  it('collapses all completed tools when active tools are running', () => {
    const done = makeDone(4);
    const active: ActiveTool[] = [
      { tool: 'send_msg', description: 'Sending message', startedAt: 2000 },
    ];
    render(<ToolCallList completedTools={done} activeTools={active} />);

    expect(screen.getByText('4 completed')).toBeInTheDocument();
    expect(screen.queryByText('Tool 2 done')).not.toBeVisible();
    expect(screen.queryByText('Tool 3 done')).not.toBeVisible();
    expect(screen.getByText('Sending message')).toBeInTheDocument();
  });

  it('shows recent completed tools once all active tools finish', () => {
    const done = makeDone(4);
    render(<ToolCallList completedTools={done} activeTools={[]} />);

    expect(screen.getByText('2 completed')).toBeInTheDocument();
    expect(screen.getByText('Tool 2 done')).toBeInTheDocument();
    expect(screen.getByText('Tool 3 done')).toBeInTheDocument();
  });

  it('hides a failure the same tool later recovered from', () => {
    const tools: CompletedTool[] = [
      {
        tool: 'save_plan',
        description: 'Save plan',
        success: false,
        startedAt: 1,
      },
      {
        tool: 'save_plan',
        description: 'Save plan again',
        success: true,
        startedAt: 2,
      },
    ];
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    expect(screen.queryByText('Save plan')).not.toBeInTheDocument();
    expect(screen.getByText('Save plan again')).toBeInTheDocument();
  });

  it('shows why a failure that stands failed', async () => {
    const tools: CompletedTool[] = [
      {
        tool: 'generate_test_set',
        description: 'Generate test set',
        success: false,
        error: 'Not in the saved plan',
        startedAt: 1,
      },
    ];
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    fireEvent.mouseOver(screen.getByText('Generate test set'));
    await waitFor(() =>
      expect(screen.getByText('Not in the saved plan')).toBeInTheDocument()
    );
  });

  it('counts failures folded into the summary', () => {
    const tools = [
      ...makeDone(1, { tool: 'broken', success: false }),
      ...makeDone(3).map((t, i) => ({
        ...t,
        tool: `ok_${i}`,
        startedAt: 10 + i,
      })),
    ];
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    expect(screen.getByText('1 completed, 1 failed')).toBeInTheDocument();
  });

  it('leaves out a zero completed count when every folded call failed', () => {
    const tools = [
      ...makeDone(2).map((t, i) => ({
        ...t,
        tool: `broken_${i}`,
        success: false,
      })),
      ...makeDone(2).map((t, i) => ({
        ...t,
        tool: `ok_${i}`,
        startedAt: 10 + i,
      })),
    ];
    render(<ToolCallList completedTools={tools} activeTools={[]} />);

    expect(screen.getByText('2 failed')).toBeInTheDocument();
  });
});
