import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import { getTestRunStatusColor, getTestRunStatusIcon } from '../TestRunStatus';

describe('getTestRunStatusColor', () => {
  it.each([
    ['completed', 'success'],
    ['partial', 'warning'],
    ['failed', 'error'],
    ['progress', 'info'],
    ['queued', 'default'],
  ])('returns "%s" for status "%s"', (status, expected) => {
    expect(getTestRunStatusColor(status)).toBe(expected);
  });

  it('is case-insensitive', () => {
    expect(getTestRunStatusColor('Completed')).toBe('success');
    expect(getTestRunStatusColor('FAILED')).toBe('error');
    expect(getTestRunStatusColor('Progress')).toBe('info');
  });

  it('returns "default" for undefined', () => {
    expect(getTestRunStatusColor(undefined)).toBe('default');
  });

  it('returns "default" for an unrecognised status', () => {
    expect(getTestRunStatusColor('running')).toBe('default');
    expect(getTestRunStatusColor('')).toBe('default');
  });
});

describe('getTestRunStatusIcon', () => {
  it.each([
    ['completed', CheckCircleOutlineIcon],
    ['partial', WarningAmberOutlinedIcon],
    ['failed', CancelOutlinedIcon],
    ['progress', PlayCircleOutlineIcon],
    ['queued', HourglassEmptyIcon],
  ])(
    'returns the correct icon component for status "%s"',
    (status, IconComponent) => {
      const icon = getTestRunStatusIcon(status);
      expect(icon.type).toBe(IconComponent);
    }
  );

  it('returns PlayArrowIcon for undefined status', () => {
    const icon = getTestRunStatusIcon(undefined);
    expect(icon.type).toBe(PlayArrowIcon);
  });

  it('returns PlayArrowIcon for an unrecognised status', () => {
    const icon = getTestRunStatusIcon('running');
    expect(icon.type).toBe(PlayArrowIcon);
  });

  it('is case-insensitive', () => {
    expect(getTestRunStatusIcon('Completed').type).toBe(CheckCircleOutlineIcon);
    expect(getTestRunStatusIcon('FAILED').type).toBe(CancelOutlinedIcon);
  });

  it('defaults to "small" font size', () => {
    const icon = getTestRunStatusIcon('completed');
    expect(icon.props.fontSize).toBe('small');
  });

  it('forwards a custom size to the icon', () => {
    const icon = getTestRunStatusIcon('completed', 'medium');
    expect(icon.props.fontSize).toBe('medium');
  });

  it('renders an SVG element for every status', () => {
    const statuses = [
      'completed',
      'partial',
      'failed',
      'progress',
      'queued',
      undefined,
    ];
    statuses.forEach(status => {
      const icon = getTestRunStatusIcon(status);
      const { container } = render(<>{icon}</>);
      expect(container.querySelector('svg')).not.toBeNull();
    });
  });
});
