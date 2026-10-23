/**
 * Exports an Architect chart as CSV, SVG or PNG, all in the browser. MUI X's own
 * export is Pro-only, so the image comes from serializing the rendered SVG with its
 * computed styles inlined, plus a title and legend (MUI renders the legend as HTML).
 */

import { ArchitectChartSpec, dataColumns } from '@/utils/architect/charts';

export interface LegendEntry {
  label: string;
  color: string;
}

export interface ChartImageOptions {
  title: string;
  legend: LegendEntry[];
  background: string;
  textColor: string;
  fontFamily: string;
}

export interface ChartImage {
  markup: string;
  width: number;
  height: number;
}

const SVG_NS = 'http://www.w3.org/2000/svg';
// Icons inside the chart (legend marks, buttons) are smaller than this; the plot never is.
const MIN_PLOT_SIDE = 48;
const PADDING = 16;
const TITLE_HEIGHT = 24;
const TITLE_FONT_SIZE = 14;
const LEGEND_HEIGHT = 24;
const LEGEND_FONT_SIZE = 12;
const LEGEND_MARK = 12;
const LEGEND_GAP = 6;
const LEGEND_ITEM_GAP = 16;
const PNG_SCALE = 2;
// The properties MUI X sets through class names rather than attributes.
const INLINED_STYLES = [
  'fill',
  'fill-opacity',
  'stroke',
  'stroke-width',
  'stroke-opacity',
  'stroke-dasharray',
  'opacity',
  'font-family',
  'font-size',
  'font-weight',
  'text-anchor',
  'dominant-baseline',
  'visibility',
  'display',
];

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** The chart's rows as CSV, raw values (ISO periods, unrounded numbers) for reuse. */
export function chartCsv(spec: ArchitectChartSpec): string {
  const columns = dataColumns(spec);
  const lines = [
    columns.map(csvCell).join(','),
    ...spec.rows.map(row => columns.map(c => csvCell(row[c])).join(',')),
  ];
  return `${lines.join('\n')}\n`;
}

export function chartFileName(spec: ArchitectChartSpec, extension: string) {
  const slug = spec.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return `${slug || 'chart'}.${extension}`;
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** The plot's SVG: the largest one, since legend marks and icons are SVGs too. */
export function findChartSvg(
  container: HTMLElement | null
): SVGSVGElement | null {
  if (!container) return null;
  let best: SVGSVGElement | null = null;
  let bestArea = 0;
  for (const svg of Array.from(container.querySelectorAll('svg'))) {
    const { width, height } = svg.getBoundingClientRect();
    if (width < MIN_PLOT_SIDE || height < MIN_PLOT_SIDE) continue;
    if (width * height > bestArea) {
      best = svg;
      bestArea = width * height;
    }
  }
  return best;
}

function inlineStyles(source: Element, target: Element) {
  const computed = getComputedStyle(source);
  target.setAttribute(
    'style',
    INLINED_STYLES.map(p => `${p}:${computed.getPropertyValue(p)}`).join(';')
  );
  Array.from(source.children).forEach((child, i) => {
    const copy = target.children[i];
    if (copy) inlineStyles(child, copy);
  });
}

function svgElement(name: string, attributes: Record<string, string | number>) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  return element;
}

function textWidth(text: string, font: string): number {
  const context = document.createElement('canvas').getContext('2d');
  if (!context) return text.length * LEGEND_FONT_SIZE * 0.6;
  context.font = font;
  return context.measureText(text).width;
}

/** A standalone SVG of the chart, with its title and legend drawn in. */
export function chartSvg(
  plot: SVGSVGElement,
  options: ChartImageOptions
): ChartImage {
  const { width: plotWidth, height: plotHeight } = plot.getBoundingClientRect();
  const legendHeight = options.legend.length ? LEGEND_HEIGHT : 0;
  const plotTop = PADDING + TITLE_HEIGHT + legendHeight;
  const width = Math.ceil(plotWidth + 2 * PADDING);
  const height = Math.ceil(plotTop + plotHeight + PADDING);

  const root = svgElement('svg', {
    xmlns: SVG_NS,
    width,
    height,
    viewBox: `0 0 ${width} ${height}`,
  });
  root.appendChild(
    svgElement('rect', { width, height, fill: options.background })
  );

  const title = svgElement('text', {
    x: PADDING,
    y: PADDING + TITLE_FONT_SIZE,
    fill: options.textColor,
    'font-family': options.fontFamily,
    'font-size': TITLE_FONT_SIZE,
    'font-weight': 600,
  });
  title.textContent = options.title;
  root.appendChild(title);

  let cursor = PADDING;
  const legendY = PADDING + TITLE_HEIGHT + LEGEND_FONT_SIZE;
  const legendFont = `${LEGEND_FONT_SIZE}px ${options.fontFamily}`;
  for (const entry of options.legend) {
    root.appendChild(
      svgElement('rect', {
        x: cursor,
        y: legendY - LEGEND_MARK + 2,
        width: LEGEND_MARK,
        height: LEGEND_MARK,
        rx: 2,
        fill: entry.color,
      })
    );
    const label = svgElement('text', {
      x: cursor + LEGEND_MARK + LEGEND_GAP,
      y: legendY,
      fill: options.textColor,
      'font-family': options.fontFamily,
      'font-size': LEGEND_FONT_SIZE,
    });
    label.textContent = entry.label;
    root.appendChild(label);
    cursor +=
      LEGEND_MARK +
      LEGEND_GAP +
      textWidth(entry.label, legendFont) +
      LEGEND_ITEM_GAP;
  }

  const copy = plot.cloneNode(true) as SVGSVGElement;
  inlineStyles(plot, copy);
  copy.setAttribute('x', String(PADDING));
  copy.setAttribute('y', String(plotTop));
  copy.setAttribute('width', String(plotWidth));
  copy.setAttribute('height', String(plotHeight));
  root.appendChild(copy);

  return {
    markup: new XMLSerializer().serializeToString(root),
    width,
    height,
  };
}

/** Renders the SVG onto a canvas at twice its size, so the PNG stays sharp. */
export async function chartPng(image: ChartImage): Promise<Blob> {
  const url = URL.createObjectURL(
    new Blob([image.markup], { type: 'image/svg+xml;charset=utf-8' })
  );
  try {
    const element = new Image();
    await new Promise<void>((resolve, reject) => {
      element.onload = () => resolve();
      element.onerror = () =>
        reject(new Error('The chart image failed to load'));
      element.src = url;
    });
    const canvas = document.createElement('canvas');
    canvas.width = image.width * PNG_SCALE;
    canvas.height = image.height * PNG_SCALE;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('No canvas to draw the chart on');
    context.scale(PNG_SCALE, PNG_SCALE);
    context.drawImage(element, 0, 0, image.width, image.height);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        blob =>
          blob ? resolve(blob) : reject(new Error('The PNG could not be made')),
        'image/png'
      )
    );
  } finally {
    URL.revokeObjectURL(url);
  }
}
