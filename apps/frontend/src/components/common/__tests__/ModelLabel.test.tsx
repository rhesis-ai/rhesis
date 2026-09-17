import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  it('reveals the full list on hover when several models contributed', async () => {
    render(
      <ModelLabel
        models={['gpt-4o', 'claude-sonnet-4']}
        providers={['openai', 'anthropic']}
      />
    );

    fireEvent.mouseOver(screen.getByText('openai/gpt-4o +1'));

    await waitFor(() =>
      expect(screen.getByRole('tooltip')).toHaveTextContent(
        'gpt-4o, claude-sonnet-4'
      )
    );
  });

  it('shows no tooltip when the one model is already named in full', async () => {
    render(<ModelLabel models={['gpt-4o']} providers={['openai']} />);

    fireEvent.mouseOver(screen.getByText('openai/gpt-4o'));

    await waitFor(() =>
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    );
  });

  it('renders inline when asked, so it can sit inside another paragraph', () => {
    // A <p> nested in a <p> is invalid markup and React warns about it.
    const { container } = render(
      <ModelLabel models={['gpt-4o']} providers={['openai']} component="span" />
    );

    expect(container.querySelector('span')).toHaveTextContent('openai/gpt-4o');
    expect(container.querySelector('p')).toBeNull();
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
