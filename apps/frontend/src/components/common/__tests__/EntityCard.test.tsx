import React from 'react';
import { render, screen } from '@testing-library/react';
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

    expect(screen.getByText('My Entity').closest('.MuiButtonBase-root')).toHaveStyle(
      {
        justifyContent: 'flex-start',
      }
    );
  });
});
