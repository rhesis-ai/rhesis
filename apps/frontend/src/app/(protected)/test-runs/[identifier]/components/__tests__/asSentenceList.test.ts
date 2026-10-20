import { asSentenceList } from '../TestDetailOverviewTab';

describe('asSentenceList', () => {
  it('lists separate sentences on one line', () => {
    expect(
      asSentenceList('Must not ask questions. Must not reassure the user.')
    ).toBe('- Must not ask questions.\n- Must not reassure the user.');
  });

  it('does not split after an abbreviation', () => {
    expect(asSentenceList('Avoid jargon, e.g. Latin terms. Be brief.')).toBe(
      '- Avoid jargon, e.g. Latin terms.\n- Be brief.'
    );
  });

  it('leaves a single sentence and text with lines alone', () => {
    expect(asSentenceList('Must not reassure.')).toBe('Must not reassure.');
    expect(asSentenceList('One.\nTwo.')).toBe('One.\nTwo.');
  });
});
