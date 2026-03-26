import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

  it('renders the icon', () => {
    render(<EntityCard {...defaultProps} />);

    expect(screen.getByTestId('icon')).toBeInTheDocument();
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

  it('renders chip section labels when provided', () => {
    render(
      <EntityCard
        {...defaultProps}
        chipSections={[
          {
            label: 'Metrics',
            chips: [{ key: 'metric-1', label: 'Accuracy' }],
          },
        ]}
      />
    );

    expect(screen.getByText('Metrics')).toBeInTheDocument();
    expect(screen.getByText('Accuracy')).toBeInTheDocument();
  });

  it('renders empty state with no chips', () => {
    render(<EntityCard {...defaultProps} chipSections={[{ chips: [] }]} />);

    expect(screen.getByText('My Entity')).toBeInTheDocument();
  });

  it('calls onClick when card is clicked', () => {
    const handleClick = jest.fn();
    render(<EntityCard {...defaultProps} onClick={handleClick} />);

    fireEvent.click(screen.getByText('My Entity'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders delete button when onDelete is provided', () => {
    const handleDelete = jest.fn();
    render(<EntityCard {...defaultProps} onDelete={handleDelete} />);

    const deleteButton = screen.getByRole('button', { name: /delete/i });
    expect(deleteButton).toBeInTheDocument();
  });

  it('calls onDelete when delete button is clicked', () => {
    const handleDelete = jest.fn();
    render(<EntityCard {...defaultProps} onDelete={handleDelete} />);

    const deleteButton = screen.getByRole('button', { name: /delete/i });
    fireEvent.click(deleteButton);
    expect(handleDelete).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when delete button is clicked', () => {
    const handleClick = jest.fn();
    const handleDelete = jest.fn();
    render(
      <EntityCard
        {...defaultProps}
        onClick={handleClick}
        onDelete={handleDelete}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /delete/i });
    fireEvent.click(deleteButton);
    expect(handleDelete).toHaveBeenCalledTimes(1);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('renders owner name and avatar when provided', () => {
    render(
      <EntityCard
        {...defaultProps}
        ownerName="Jessica"
        ownerAvatar="https://example.com/avatar.jpg"
      />
    );

    expect(screen.getByText('Jessica')).toBeInTheDocument();
    expect(screen.getByAltText('Jessica')).toBeInTheDocument();
  });

  it('does not render owner section when ownerName is not provided', () => {
    render(<EntityCard {...defaultProps} />);

    expect(screen.queryByText('Jessica')).not.toBeInTheDocument();
  });

  it('renders status badge when statusLabel is provided', () => {
    render(
      <EntityCard
        {...defaultProps}
        statusLabel="Active"
        statusColor="success"
      />
    );

    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('does not render status badge when statusLabel is not provided', () => {
    render(<EntityCard {...defaultProps} />);

    expect(screen.queryByText('Active')).not.toBeInTheDocument();
  });
});
