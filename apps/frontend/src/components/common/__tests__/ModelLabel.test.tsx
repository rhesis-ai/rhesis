import { render, screen } from '@testing-library/react';
import ModelLabel from '../ModelLabel';

describe('ModelLabel', () => {
  it('qualifies the model with its provider', () => {
    render(<ModelLabel models={['gpt-4o']} providers={['openai']} />);
    expect(screen.getByText('openai/gpt-4o')).toBeInTheDocument();
  });

  it('counts the rest when several models contributed', () => {
    render(
      <ModelLabel models={['a', 'b', 'c']} providers={['openai', 'gemini']} />
    );
    expect(screen.getByText('openai/a +2')).toBeInTheDocument();
  });

  it('falls back to the bare model when no provider is known', () => {
    render(<ModelLabel models={['some-self-hosted']} providers={[]} />);
    expect(screen.getByText('some-self-hosted')).toBeInTheDocument();
  });

  it('shows a dash when nothing was priced', () => {
    // A dash rather than a blank: the row still occupies the column, and blank
    // reads as an oversight where a dash reads as "we do not know".
    render(<ModelLabel models={[]} providers={[]} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('survives undefined, which is what an older API response sends', () => {
    render(<ModelLabel />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
