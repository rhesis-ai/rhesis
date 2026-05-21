import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FilterButton } from '../FilterButton';

describe('FilterButton', () => {
  it('renders filter control with default label', () => {
    render(<FilterButton onClick={() => {}} />);
    expect(screen.getByRole('button', { name: 'Filters' })).toBeInTheDocument();
  });

  it('shows active indicator when hasActiveFilters is true', () => {
    const { container } = render(
      <FilterButton onClick={() => {}} hasActiveFilters />
    );
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument();
  });

  it('calls onClick when pressed', async () => {
    const user = userEvent.setup();
    const onClick = jest.fn();
    render(<FilterButton onClick={onClick} />);
    await user.click(screen.getByRole('button', { name: 'Filters' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
