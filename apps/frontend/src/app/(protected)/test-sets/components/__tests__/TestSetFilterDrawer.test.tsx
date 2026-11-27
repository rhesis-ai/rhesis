import React from 'react';
import { render, screen, fireEvent, within } from '@/test-utils';
import '@testing-library/jest-dom';

import TestSetFilterDrawer, {
  EMPTY_TEST_SET_FILTERS,
} from '../TestSetFilterDrawer';
import { EntityType } from '@/types/entity-type';

const mockUseTags = jest.fn();

jest.mock('@/hooks/useLookups', () => ({
  useStatuses: () => ({ data: [], isLoading: false }),
  useUsers: () => ({ data: [], isLoading: false }),
  useTags: (...args: unknown[]) => mockUseTags(...args),
}));

beforeEach(() => {
  mockUseTags.mockReset();
  mockUseTags.mockReturnValue({
    data: [
      { id: '1', name: 'nightly' },
      { id: '2', name: 'release' },
      { id: '3', name: 'regression' },
    ],
    isLoading: false,
  });
});

function renderDrawer() {
  const onApply = jest.fn();
  render(
    <TestSetFilterDrawer
      open
      onClose={jest.fn()}
      filters={EMPTY_TEST_SET_FILTERS}
      onApply={onApply}
    />
  );
  return { onApply };
}

describe('TestSetFilterDrawer tag field', () => {
  it('suggests only tags used on test sets', () => {
    renderDrawer();
    expect(mockUseTags).toHaveBeenCalledWith(true, EntityType.TEST_SET);
  });

  it('narrows the suggestions as you type', () => {
    renderDrawer();
    const input = screen.getByPlaceholderText('Select tag…');

    fireEvent.change(input, { target: { value: 're' } });
    let options = within(screen.getByRole('listbox')).getAllByRole('option');
    expect(options.map(o => o.textContent)).toEqual(['release', 'regression']);

    fireEvent.change(input, { target: { value: 'rel' } });
    options = within(screen.getByRole('listbox')).getAllByRole('option');
    expect(options.map(o => o.textContent)).toEqual(['release']);
  });

  it('applies a typed tag that is not in the list', () => {
    const { onApply } = renderDrawer();
    fireEvent.change(screen.getByPlaceholderText('Select tag…'), {
      target: { value: 'custom' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ tag: 'custom' })
    );
  });

  it('applies a picked suggestion', () => {
    const { onApply } = renderDrawer();
    const input = screen.getByPlaceholderText('Select tag…');
    fireEvent.change(input, { target: { value: 'rel' } });
    fireEvent.click(screen.getByRole('option', { name: 'release' }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ tag: 'release' })
    );
  });
});
