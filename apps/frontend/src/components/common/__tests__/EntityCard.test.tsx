import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EntityCard from '../EntityCard';

const defaultProps = {
  icon: <span data-testid="icon">★</span>,
  title: 'My Entity',
  description: 'A helpful description',
};

describe('EntityCard', () => {
  it('renders title and description', () => {
    render(<EntityCard {...defaultProps} />);

    expect(screen.getByText('My Entity')).toBeInTheDocument();
    expect(screen.getByText('A helpful description')).toBeInTheDocument();
  });

  it('renders the icon when provided', () => {
    render(<EntityCard {...defaultProps} />);

    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('does not render an icon slot when icon is omitted', () => {
    const { icon: _icon, ...propsWithoutIcon } = defaultProps;
    render(<EntityCard {...propsWithoutIcon} />);

    expect(screen.queryByTestId('icon')).not.toBeInTheDocument();
  });

  it('renders the context line', () => {
    render(<EntityCard {...defaultProps} context="Reliability ›" />);

    expect(screen.getByTestId('entity-card-context')).toHaveTextContent(
      'Reliability ›'
    );
  });

  it('joins plain facts with a dot, but not chips or states', () => {
    render(
      <EntityCard
        {...defaultProps}
        facts={[
          { key: 'type', kind: 'type', label: 'Compliance' },
          { key: 'impact', kind: 'state', label: 'Reputation impact' },
          { key: 'a', kind: 'plain', label: 'Single-turn' },
          { key: 'b', kind: 'plain', label: 'Multi-turn' },
        ]}
      />
    );

    expect(screen.getByTestId('entity-card-facts')).toHaveTextContent(
      'ComplianceReputation impactSingle-turn·Multi-turn'
    );
  });

  it('renders counted relations and greys out zero counts', () => {
    render(
      <EntityCard
        {...defaultProps}
        relations={[
          { key: 'metrics', count: 7, label: 'metrics' },
          { key: 'sources', count: 0, label: 'sources' },
        ]}
      />
    );

    const relations = screen.getByTestId('entity-card-relations');
    expect(relations).toHaveTextContent('7 metrics');
    expect(screen.getByText('7')).not.toHaveStyle({ fontWeight: 400 });
    expect(screen.getByText('0')).toHaveStyle({ fontWeight: 400 });
  });

  it('shows the owner and when it was updated in the footer', () => {
    render(
      <EntityCard
        {...defaultProps}
        userName="Local User"
        updatedAt={new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString()}
      />
    );

    expect(screen.getByText('Local')).toBeInTheDocument();
    expect(screen.getByText('Updated 3 days ago')).toBeInTheDocument();
  });

  it('puts a footer action in place of the updated time', () => {
    render(
      <EntityCard
        {...defaultProps}
        updatedAt={new Date().toISOString()}
        footerAction={<button>Request access</button>}
      />
    );

    expect(
      screen.getByRole('button', { name: 'Request access' })
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Updated/)).not.toBeInTheDocument();
  });

  it('renders topRightActions when provided', () => {
    render(
      <EntityCard
        {...defaultProps}
        topRightActions={<button data-testid="edit-btn">Edit</button>}
      />
    );

    expect(screen.getByTestId('edit-btn')).toBeInTheDocument();
  });

  it('reserves min height for two description lines when text is short', () => {
    render(<EntityCard {...defaultProps} description="Short text" />);

    expect(screen.getByTestId('entity-card-description')).toHaveStyle({
      minHeight: '44px',
    });
  });

  it('reserves description height when description is omitted', () => {
    const { description: _description, ...propsWithoutDescription } =
      defaultProps;
    render(<EntityCard {...propsWithoutDescription} />);

    expect(screen.getByTestId('entity-card-description')).toHaveStyle({
      minHeight: '44px',
    });
  });

  it('top-aligns card content in stretched grid layouts', () => {
    render(<EntityCard {...defaultProps} />);

    expect(
      screen.getByText('My Entity').closest('.MuiButtonBase-root')
    ).toHaveStyle({
      justifyContent: 'flex-start',
    });
  });
  describe('delete button', () => {
    it('names the delete button and fires onDelete when enabled', async () => {
      const onDelete = jest.fn();
      render(<EntityCard {...defaultProps} onDelete={onDelete} />);

      const button = screen.getByRole('button', { name: 'Delete' });
      expect(button).toBeEnabled();

      await userEvent.click(button);
      expect(onDelete).toHaveBeenCalledTimes(1);
    });

    it('uses deleteLabel as the accessible name', () => {
      render(
        <EntityCard
          {...defaultProps}
          onDelete={jest.fn()}
          deleteLabel="Delete project"
        />
      );

      expect(
        screen.getByRole('button', { name: 'Delete project' })
      ).toBeInTheDocument();
    });

    it('disables the delete button and swallows clicks when a reason is given', async () => {
      const onDelete = jest.fn();
      render(
        <EntityCard
          {...defaultProps}
          onDelete={onDelete}
          deleteDisabledReason="Active project — cannot be deleted."
        />
      );

      const button = screen.getByRole('button', { name: 'Delete' });
      expect(button).toBeDisabled();
      // MUI puts pointer-events: none on a disabled button, so a real click never
      // reaches it — the span wrapper absorbs it.
      expect(button).toHaveStyle({ pointerEvents: 'none' });

      await userEvent.click(button.parentElement as HTMLElement);
      expect(onDelete).not.toHaveBeenCalled();
    });

    it('shows the reason as the tooltip on the disabled delete button', async () => {
      render(
        <EntityCard
          {...defaultProps}
          onDelete={jest.fn()}
          deleteDisabledReason="Active project — cannot be deleted."
        />
      );

      // Hovering the wrapper, not the button: MUI sets pointer-events: none on a
      // disabled button, which is exactly why the span wrapper exists.
      const wrapper = screen.getByRole('button', { name: 'Delete' })
        .parentElement as HTMLElement;
      await userEvent.hover(wrapper);

      expect(
        await screen.findByRole('tooltip', {
          name: 'Active project — cannot be deleted.',
        })
      ).toBeInTheDocument();
    });

    it('keeps the title clear of the top-right slot when delete is disabled', () => {
      render(
        <EntityCard
          {...defaultProps}
          onDelete={jest.fn()}
          deleteDisabledReason="Nope"
        />
      );

      expect(screen.getByText('My Entity')).toHaveStyle({
        paddingRight: '36px',
      });
    });
  });
});
