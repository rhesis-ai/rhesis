import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { getTestRunStatusColor, getTestRunStatusIcon } from '../TestRunStatus';

describe('getTestRunStatusColor', () => {
  it('returns "default" for undefined status', () => {
    expect(getTestRunStatusColor(undefined)).toBe('default');
  });

  it('returns "success" for completed', () => {
    expect(getTestRunStatusColor('completed')).toBe('success');
    expect(getTestRunStatusColor('Completed')).toBe('success');
  });

  it('returns "warning" for partial', () => {
    expect(getTestRunStatusColor('partial')).toBe('warning');
    expect(getTestRunStatusColor('Partial')).toBe('warning');
  });

  it('returns "error" for failed', () => {
    expect(getTestRunStatusColor('failed')).toBe('error');
    expect(getTestRunStatusColor('Failed')).toBe('error');
  });

  it('returns "info" for progress', () => {
    expect(getTestRunStatusColor('progress')).toBe('info');
    expect(getTestRunStatusColor('Progress')).toBe('info');
  });

  it('returns "default" for unknown status', () => {
    expect(getTestRunStatusColor('unknown')).toBe('default');
    expect(getTestRunStatusColor('cancelled')).toBe('default');
  });
});

describe('getTestRunStatusIcon', () => {
  it('renders an icon for undefined status', () => {
    const icon = getTestRunStatusIcon(undefined);
    const { container } = render(<>{icon}</>);
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('renders CheckCircleOutlineIcon for completed', () => {
    const icon = getTestRunStatusIcon('completed');
    const { container } = render(<>{icon}</>);
    expect(
      container.querySelector('[data-testid="CheckCircleOutlineIcon"]')
    ).toBeInTheDocument();
  });

  it('renders WarningAmberOutlinedIcon for partial', () => {
    const icon = getTestRunStatusIcon('partial');
    const { container } = render(<>{icon}</>);
    expect(
      container.querySelector('[data-testid="WarningAmberOutlinedIcon"]')
    ).toBeInTheDocument();
  });

  it('renders CancelOutlinedIcon for failed', () => {
    const icon = getTestRunStatusIcon('failed');
    const { container } = render(<>{icon}</>);
    expect(
      container.querySelector('[data-testid="CancelOutlinedIcon"]')
    ).toBeInTheDocument();
  });

  it('renders PlayCircleOutlineIcon for progress', () => {
    const icon = getTestRunStatusIcon('progress');
    const { container } = render(<>{icon}</>);
    expect(
      container.querySelector('[data-testid="PlayCircleOutlineIcon"]')
    ).toBeInTheDocument();
  });

  it('renders default PlayArrowIcon for unknown status', () => {
    const icon = getTestRunStatusIcon('unknown');
    const { container } = render(<>{icon}</>);
    expect(
      container.querySelector('[data-testid="PlayArrowIcon"]')
    ).toBeInTheDocument();
  });

  it('supports size parameter', () => {
    const icon = getTestRunStatusIcon('completed', 'medium');
    const { container } = render(<>{icon}</>);
    const svg = container.querySelector('svg');
    expect(svg).toHaveClass('MuiSvgIcon-fontSizeMedium');
  });
});
