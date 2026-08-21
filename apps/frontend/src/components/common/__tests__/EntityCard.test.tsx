import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EntityCard from '../EntityCard';

const defaultProps = {
  icon: <span data-testid="icon">★</span>,
  title: 'My Entity',
  description: 'A helpful description',
  chipSections: [],
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

  it('renders caption text when provided', () => {
    render(
      <EntityCard {...defaultProps} captionText="Last run: Jan 1, 2024" />
    );

    expect(screen.getByText('Last run: Jan 1, 2024')).toBeInTheDocument();
  });

  it('does not render caption area when captionText is not provided', () => {
    render(<EntityCard {...defaultProps} />);

    expect(screen.queryByText('Last run:')).not.toBeInTheDocument();
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

  it('renders chips in a single section', () => {
    render(
      <EntityCard
        {...defaultProps}
        chipSections={[
          {
            chips: [
              { key: 'status', label: 'Active' },
              { key: 'type', label: 'REST' },
            ],
          },
        ]}
      />
    );

    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('REST')).toBeInTheDocument();
  });

  it('renders chips across multiple sections', () => {
    render(
      <EntityCard
        {...defaultProps}
        chipSections={[
          { chips: [{ key: 'env', label: 'Production' }] },
          { chips: [{ key: 'type', label: 'Multi-Turn' }] },
        ]}
      />
    );

    expect(screen.getByText('Production')).toBeInTheDocument();
    expect(screen.getByText('Multi-Turn')).toBeInTheDocument();
  });

  it('renders empty state with no chips', () => {
    render(<EntityCard {...defaultProps} chipSections={[{ chips: [] }]} />);

    expect(screen.getByText('My Entity')).toBeInTheDocument();
  });

  it('reserves min height for three description lines when text is short', () => {
    render(<EntityCard {...defaultProps} description="Short text" />);

    expect(screen.getByTestId('entity-card-description')).toHaveStyle({
      minHeight: '66px',
    });
  });

  it('reserves description height when description is omitted', () => {
    const { description: _description, ...propsWithoutDescription } =
      defaultProps;
    render(<EntityCard {...propsWithoutDescription} />);

    expect(screen.getByTestId('entity-card-description')).toHaveStyle({
      minHeight: '66px',
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
