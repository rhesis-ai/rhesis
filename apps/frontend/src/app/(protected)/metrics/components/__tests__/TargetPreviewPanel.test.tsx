import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';

import TargetPreviewPanel, { previewAnnouncement } from '../TargetPreviewPanel';
import type { MetricTargetPreview } from '@/utils/api-client/interfaces/metric';

const mockAnnounce = jest.fn();
jest.mock('@/components/common/LiveAnnouncer', () => ({
  useAnnounce: () => mockAnnounce,
}));

const SPANS = { one: 'span', many: 'spans' };

function preview(
  overrides: Partial<MetricTargetPreview> = {}
): MetricTargetPreview {
  return {
    traces: 12,
    matching_traces: 4,
    units: 6,
    not_applicable_traces: 8,
    samples: [],
    ...overrides,
  };
}

function renderPanel(value: MetricTargetPreview) {
  return render(
    <TargetPreviewPanel
      preview={value}
      stale={false}
      loading={false}
      error={null}
      blocked={null}
      noProject={false}
      traces={50}
      unitNoun={SPANS}
    />
  );
}

describe('TargetPreviewPanel partial results', () => {
  beforeEach(() => mockAnnounce.mockClear());

  it('says the counts cover only the traces read when the preview stopped early', () => {
    renderPanel(preview({ partial: true }));

    expect(screen.getByTestId('target-preview-partial')).toHaveTextContent(
      'these counts cover only the 12 traces it read'
    );
    expect(mockAnnounce).toHaveBeenCalledWith(
      expect.stringContaining('these counts cover only the 12 traces it read')
    );
  });

  it('says so on the nothing-matches message too', () => {
    renderPanel(preview({ partial: true, matching_traces: 0, units: 0 }));

    expect(screen.getByTestId('target-preview-no-match')).toBeInTheDocument();
    expect(screen.getByTestId('target-preview-partial')).toBeInTheDocument();
  });

  it('adds nothing when the preview read every trace', () => {
    renderPanel(preview());

    expect(
      screen.queryByTestId('target-preview-partial')
    ).not.toBeInTheDocument();
    expect(previewAnnouncement(preview(), SPANS)).not.toContain(
      'stopped early'
    );
  });
});
