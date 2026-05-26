import { isEmbeddingGraphNewerThanBaseline } from '../embeddingGraphPolling';

describe('isEmbeddingGraphNewerThanBaseline', () => {
  it('accepts any graph when there is no baseline (first compute)', () => {
    expect(
      isEmbeddingGraphNewerThanBaseline('2026-01-01T00:00:00Z', null)
    ).toBe(true);
  });

  it('rejects a graph with the same computed_at as the baseline', () => {
    expect(
      isEmbeddingGraphNewerThanBaseline(
        '2026-01-01T12:00:00Z',
        '2026-01-01T12:00:00Z'
      )
    ).toBe(false);
  });

  it('rejects a graph older than the baseline', () => {
    expect(
      isEmbeddingGraphNewerThanBaseline(
        '2026-01-01T11:00:00Z',
        '2026-01-01T12:00:00Z'
      )
    ).toBe(false);
  });

  it('accepts a graph newer than the baseline', () => {
    expect(
      isEmbeddingGraphNewerThanBaseline(
        '2026-01-01T13:00:00Z',
        '2026-01-01T12:00:00Z'
      )
    ).toBe(true);
  });
});
