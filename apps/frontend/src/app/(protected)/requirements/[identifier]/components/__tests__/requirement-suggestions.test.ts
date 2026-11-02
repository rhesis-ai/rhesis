/**
 * @jest-environment node
 */
// Node, not jsdom: jsdom has no Web Crypto, and the hash is what is tested.
import { createHash } from 'crypto';
import type {
  RequirementReviewHint,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';
import {
  RULE_HINT_MESSAGES,
  hintUpdate,
  isReviewOutdated,
  requirementTextHash,
  ruleHints,
} from '../requirement-suggestions';

type HintInput = Pick<
  RequirementWithMetrics,
  'sources' | 'examples_count' | 'metrics'
>;

const metric = { id: 'm1' } as unknown as RequirementWithMetrics['metrics'][0];
const source = {
  id: 's1',
  title: 'Policy',
} as unknown as NonNullable<RequirementWithMetrics['sources']>[0];

describe('ruleHints', () => {
  it('flags a bare requirement for source, examples and metric', () => {
    const hints = ruleHints({ metrics: [] } as HintInput);
    expect(hints.map(h => h.id)).toEqual([
      'no_source',
      'no_examples',
      'no_metric',
    ]);
    expect(hints[0].message).toBe(RULE_HINT_MESSAGES.no_source);
  });

  it('has nothing to say once all three are there', () => {
    expect(
      ruleHints({ sources: [source], examples_count: 2, metrics: [metric] })
    ).toEqual([]);
  });

  it('flags only what is missing', () => {
    expect(
      ruleHints({
        sources: [source],
        examples_count: 0,
        metrics: [metric],
      }).map(h => h.id)
    ).toEqual(['no_examples']);
  });
});

describe('requirementTextHash / isReviewOutdated', () => {
  const sha = (text: string) =>
    createHash('sha256').update(text, 'utf8').digest('hex');

  it('hashes name, a newline and the description, like the backend', async () => {
    await expect(requirementTextHash('Name', 'Some text')).resolves.toBe(
      sha('Name\nSome text')
    );
  });

  it('hashes a missing description as empty', async () => {
    await expect(requirementTextHash('Name', null)).resolves.toBe(
      sha('Name\n')
    );
  });

  it('is outdated only when the stored hash differs', async () => {
    const hash = await requirementTextHash('Name', 'Some text');
    expect(
      isReviewOutdated({ description_hash: sha('Name\nSome text') }, hash)
    ).toBe(false);
    expect(isReviewOutdated({ description_hash: sha('Name\nOld') }, hash)).toBe(
      true
    );
  });

  it('is never outdated without a review or without a hash', () => {
    expect(isReviewOutdated(null, 'abc')).toBe(false);
    expect(isReviewOutdated({ description_hash: 'abc' }, null)).toBe(false);
  });
});

describe('hintUpdate', () => {
  const types = [
    { id: 't1', type_value: 'Compliance' },
  ] as unknown as Parameters<typeof hintUpdate>[2];
  const hint = (
    over: Partial<RequirementReviewHint>
  ): RequirementReviewHint => ({
    kind: 'vague_wording',
    message: 'm',
    quote: null,
    suggestion: null,
    ...over,
  });

  it('replaces the quote in the description', () => {
    expect(
      hintUpdate(
        hint({ quote: 'appropriately', suggestion: 'by offering an advisor' }),
        'respond appropriately.',
        types
      )
    ).toEqual({ description: 'respond by offering an advisor.' });
  });

  it('replaces the whole description when there is no quote to find', () => {
    expect(
      hintUpdate(hint({ suggestion: 'New text' }), 'Old text', types)
    ).toEqual({ description: 'New text' });
  });

  it('sets a type by matching its name, or does nothing when none matches', () => {
    expect(
      hintUpdate(
        hint({ kind: 'suggest_type', suggestion: 'compliance' }),
        'x',
        types
      )
    ).toEqual({ requirement_type_id: 't1' });
    expect(
      hintUpdate(hint({ kind: 'suggest_type', suggestion: 'Tone' }), 'x', types)
    ).toBeNull();
  });

  it('has nothing to apply without a suggestion', () => {
    expect(hintUpdate(hint({ quote: 'x' }), 'x', types)).toBeNull();
  });
});
