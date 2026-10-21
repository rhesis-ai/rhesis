import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { FormattedText, asSentenceList } from '@/components/common/TestText';

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

describe('FormattedText', () => {
  it('lists plain sentences when asked', () => {
    render(<FormattedText text="Must not X. Must not Y." sentences />);
    expect(screen.getByText('Must not X.')).toBeInTheDocument();
    expect(screen.getByText('Must not Y.')).toBeInTheDocument();
  });

  it('keeps markdown as markdown instead of splitting it', () => {
    render(<FormattedText text="Never give a **dosage**." sentences />);
    expect(screen.getByText('dosage').tagName).toBe('STRONG');
  });
});
