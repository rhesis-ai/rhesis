import { render, screen } from '@testing-library/react';
import TaskProgressList from '../TaskProgressList';
import { TaskProgressEntry } from '@/hooks/useArchitectChat';

function makeEntry(
  partial: Partial<TaskProgressEntry> & {
    label: string;
    status: TaskProgressEntry['status'];
  }
): TaskProgressEntry {
  return {
    taskId: 'task-1',
    receivedAt: Date.now(),
    ...partial,
  };
}

describe('TaskProgressList', () => {
  it('renders nothing when the entries array is empty', () => {
    const { container } = render(
      <TaskProgressList entries={[]} isAwaiting={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders each entry with its label', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({ status: 'started', label: 'Starting exploration' }),
      makeEntry({ status: 'progress', label: 'Running domain probing' }),
      makeEntry({ status: 'completed', label: 'Exploration completed' }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting={false} />);

    expect(screen.getByText('Starting exploration')).toBeInTheDocument();
    expect(screen.getByText('Running domain probing')).toBeInTheDocument();
    expect(screen.getByText('Exploration completed')).toBeInTheDocument();
  });

  it('shows a live spinner only on the latest entry while still awaiting', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({ status: 'progress', label: 'Step one' }),
      makeEntry({ status: 'progress', label: 'Step two (current)' }),
    ];

    const { container } = render(
      <TaskProgressList entries={entries} isAwaiting />
    );

    // Exactly one MUI CircularProgress (the live spinner) should
    // appear in the entire list.
    const progressbars = container.querySelectorAll(
      '.MuiCircularProgress-root'
    );
    expect(progressbars).toHaveLength(1);
  });

  it('shows no spinner when isAwaiting is false', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({ status: 'progress', label: 'Step one' }),
      makeEntry({ status: 'progress', label: 'Step two' }),
    ];

    const { container } = render(
      <TaskProgressList entries={entries} isAwaiting={false} />
    );

    const progressbars = container.querySelectorAll(
      '.MuiCircularProgress-root'
    );
    expect(progressbars).toHaveLength(0);
  });

  it('renders a checkmark next to a completed entry', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({ status: 'completed', label: 'Exploration completed' }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting={false} />);

    expect(screen.getByTestId('CheckCircleOutlineIcon')).toBeInTheDocument();
  });

  it('renders an error icon next to a failed entry', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({ status: 'failed', label: 'Exploration failed' }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting={false} />);

    expect(screen.getByTestId('ErrorOutlineIcon')).toBeInTheDocument();
  });

  it('appends "(step/total)" when both are provided', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({
        status: 'progress',
        label: 'Penelope turn',
        step: 3,
        total: 8,
      }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting />);

    expect(screen.getByText('(3/8)')).toBeInTheDocument();
  });

  it('renders only "(step)" when total is missing', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({ status: 'progress', label: 'Turn', step: 2 }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting />);

    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('appends a formatted duration when present', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({
        status: 'completed',
        label: 'Done',
        durationMs: 1500,
      }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting={false} />);

    expect(screen.getByText('1.5s')).toBeInTheDocument();
  });

  it('formats sub-second durations in milliseconds', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({
        status: 'completed',
        label: 'Done',
        durationMs: 250,
      }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting={false} />);

    expect(screen.getByText('250ms')).toBeInTheDocument();
  });

  it('formats multi-minute durations as Xm Ys', () => {
    const entries: TaskProgressEntry[] = [
      makeEntry({
        status: 'completed',
        label: 'Comprehensive exploration',
        durationMs: 125_000,
      }),
    ];

    render(<TaskProgressList entries={entries} isAwaiting={false} />);

    expect(screen.getByText('2m 5s')).toBeInTheDocument();
  });
});
