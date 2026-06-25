import {
  readInsightsEndpointId,
  writeInsightsEndpointId,
  clearInsightsEndpointId,
  INSIGHTS_ENDPOINT_COOKIE,
} from '../insights-endpoint';

describe('insights-endpoint cookie helpers', () => {
  beforeEach(() => {
    document.cookie = `${INSIGHTS_ENDPOINT_COOKIE}=; path=/; max-age=0`;
  });

  it('writes and reads endpoint id', () => {
    writeInsightsEndpointId('endpoint-123');
    expect(readInsightsEndpointId()).toBe('endpoint-123');
  });

  it('clears endpoint id', () => {
    writeInsightsEndpointId('endpoint-123');
    clearInsightsEndpointId();
    expect(readInsightsEndpointId()).toBeNull();
  });
});
