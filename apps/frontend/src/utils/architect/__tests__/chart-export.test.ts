import type { ArchitectChartSpec } from '../charts';
import { chartCsv, chartFileName, findChartSvg } from '../chart-export';

const spec: ArchitectChartSpec = {
  title: 'Pass rate by topic, last 30 days',
  chart_type: 'bar',
  x: 'topic',
  series: 'period',
  measures: [{ key: 'pass_rate', kind: 'rate' }],
  time_grain: 'week',
  rows: [
    { topic: 'Visa, documents', period: '2026-09-07', pass_rate: 56.5217 },
    { topic: 'Say "hi"', period: '2026-09-07', pass_rate: null },
  ],
};

describe('architect chart export', () => {
  it('writes raw values as CSV and quotes what needs it', () => {
    expect(chartCsv(spec)).toBe(
      'topic,period,pass_rate\n' +
        '"Visa, documents",2026-09-07,56.5217\n' +
        '"Say ""hi""",2026-09-07,\n'
    );
  });

  it('names the file after the title', () => {
    expect(chartFileName(spec, 'png')).toBe(
      'pass-rate-by-topic-last-30-days.png'
    );
    expect(chartFileName({ ...spec, title: '!!!' }, 'csv')).toBe('chart.csv');
  });

  it('picks the plot over small icon svgs', () => {
    const container = document.createElement('div');
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const plot = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    container.append(icon, plot);
    const size = (width: number, height: number) =>
      ({ width, height }) as DOMRect;
    icon.getBoundingClientRect = () => size(12, 12);
    plot.getBoundingClientRect = () => size(600, 280);

    expect(findChartSvg(container)).toBe(plot);
    expect(findChartSvg(null)).toBeNull();
  });
});
