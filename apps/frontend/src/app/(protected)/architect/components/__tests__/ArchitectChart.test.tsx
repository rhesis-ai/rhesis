import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import ArchitectChart, { ArchitectChartBoundary } from '../ArchitectChart';
import type { ArchitectChartSpec } from '@/utils/architect/charts';

// MUI X charts measure the DOM, which jsdom can't; render what they were given.
// A function declaration so it is hoisted above the jest.mock calls that use it.
function mockFakeChart(name: string) {
  return function FakeChart({
    series,
  }: {
    series: Array<{ label?: string; color?: string }>;
  }) {
    return (
      <div data-testid={name}>
        {series.map(s => (
          <span key={s.label ?? name} data-color={s.color}>
            {s.label}
          </span>
        ))}
      </div>
    );
  };
}
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));
jest.mock('@mui/x-charts/BarChart', () => ({ BarChart: mockFakeChart('bar') }));
jest.mock('@mui/x-charts/LineChart', () => ({
  LineChart: mockFakeChart('line'),
}));
jest.mock('@mui/x-charts/ScatterChart', () => ({
  ScatterChart: mockFakeChart('scatter'),
}));
jest.mock('@mui/x-charts/RadarChart', () => ({
  RadarChart: mockFakeChart('radar'),
}));
jest.mock('@mui/x-charts/ChartsReferenceLine', () => ({
  ChartsReferenceLine: () => null,
}));

function renderChart(spec: ArchitectChartSpec) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <ArchitectChart spec={spec} />
    </ThemeProvider>
  );
}

const topics: ArchitectChartSpec = {
  title: 'Weakest topics',
  chart_type: 'horizontal_bar',
  x: 'topic',
  measures: [{ key: 'pass_rate', kind: 'rate' }],
  rows: [
    { topic: 'Claims', topic_id: 't1', pass_rate: 25 },
    { topic: 'Billing', topic_id: 't2', pass_rate: 60 },
  ],
};

describe('ArchitectChart', () => {
  it('draws a bar chart with the title', () => {
    renderChart(topics);

    expect(screen.getByText('Weakest topics')).toBeInTheDocument();
    expect(screen.getByTestId('bar')).toHaveTextContent('Pass rate');
  });

  it('switches to the exact numbers and back', () => {
    renderChart(topics);

    fireEvent.click(screen.getByRole('button', { name: 'Show data' }));
    expect(screen.getByText('Claims')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Show chart' }));
    expect(screen.getByTestId('bar')).toBeInTheDocument();
  });

  it('draws one line per series value', () => {
    renderChart({
      title: 'Weekly pass rate',
      chart_type: 'line',
      x: 'period',
      series: 'endpoint',
      time_grain: 'week',
      measures: [{ key: 'pass_rate', kind: 'rate' }],
      rows: [
        { period: '2026-08-31', endpoint: 'Bot A', pass_rate: 70 },
        { period: '2026-08-31', endpoint: 'Bot B', pass_rate: 50 },
      ],
    });

    expect(screen.getByTestId('line')).toHaveTextContent('Bot A');
    expect(screen.getByTestId('line')).toHaveTextContent('Bot B');
  });

  it('draws series in the architect palette, never the brand blue', () => {
    const { series } = lightTheme.chartPalettes.architect;
    renderChart({
      title: 'Weekly pass rate',
      chart_type: 'line',
      x: 'period',
      series: 'endpoint',
      measures: [{ key: 'pass_rate', kind: 'rate' }],
      rows: [
        { period: '2026-08-31', endpoint: 'Bot A', pass_rate: 70 },
        { period: '2026-08-31', endpoint: 'Bot B', pass_rate: 50 },
      ],
    });

    expect(screen.getByText('Bot A')).toHaveAttribute('data-color', series[0]);
    expect(screen.getByText('Bot B')).toHaveAttribute('data-color', series[1]);
  });

  it('exports the data as CSV', () => {
    const createObjectURL = jest.fn(() => 'blob:chart');
    Object.assign(URL, { createObjectURL, revokeObjectURL: jest.fn() });
    const click = jest
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});
    renderChart(topics);

    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
    // jsdom lays nothing out, so there is no plot to export as an image.
    expect(screen.queryByText('Image (PNG)')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Data (CSV)'));

    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(click).toHaveBeenCalled();
    click.mockRestore();
  });

  it('renders a heat table with a cell per pair', () => {
    renderChart({
      title: 'Topic by run',
      chart_type: 'heat_table',
      x: 'topic',
      series: 'test_run',
      measures: [{ key: 'pass_rate', kind: 'rate' }],
      rows: [
        { topic: 'Claims', test_run: 'Run A', pass_rate: 50 },
        { topic: 'Claims', test_run: 'Run B', pass_rate: 0 },
        { topic: 'Billing', test_run: 'Run A', pass_rate: 100 },
      ],
    });

    expect(screen.getByText('Run B')).toBeInTheDocument();
    expect(screen.getByText('0%')).toBeInTheDocument();
    // Billing never ran in Run B.
    expect(screen.getByText('–')).toBeInTheDocument();
  });

  it('shows a headline number for kpi with export but no data toggle', () => {
    renderChart({
      title: 'Overall',
      chart_type: 'kpi',
      measures: [{ key: 'pass_rate', kind: 'rate' }],
      target: 90,
      rows: [{ pass_rate: 58.33 }],
    });

    expect(screen.getByText('58.3%')).toBeInTheDocument();
    expect(screen.getByText(/target 90%/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Show data' })
    ).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument();
  });

  it('notes when rows were cut off', () => {
    renderChart({ ...topics, truncated: true });

    expect(screen.getByText('Showing the first 2 rows.')).toBeInTheDocument();
  });
});

describe('ArchitectChartBoundary', () => {
  it('replaces a chart that throws with a note', () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const Broken = () => {
      throw new Error('bad spec');
    };

    render(
      <ArchitectChartBoundary title="Broken chart">
        <Broken />
      </ArchitectChartBoundary>
    );

    expect(
      screen.getByText('The chart “Broken chart” could not be shown.')
    ).toBeInTheDocument();
    spy.mockRestore();
  });
});
