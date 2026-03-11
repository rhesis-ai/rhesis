import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import BaseTag from '../BaseTag';

// Mock API-related dependencies (not needed when no entity is provided)
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn(),
}));

jest.mock('@/utils/api-client/tags-client', () => ({
  TagsClient: jest.fn(),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

function renderTag(
  value: string[],
  onChange: jest.Mock,
  props: Record<string, unknown> = {}
) {
  return render(
    <BaseTag
      value={value}
      onChange={onChange}
      placeholder="Add tag..."
      {...props}
    />
  );
}

describe('BaseTag', () => {
  let onChange: jest.Mock;

  beforeEach(() => {
    onChange = jest.fn();
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it('renders existing tags as chips', () => {
    renderTag(['react', 'typescript'], onChange);
    expect(screen.getByText('react')).toBeInTheDocument();
    expect(screen.getByText('typescript')).toBeInTheDocument();
  });

  it('renders an input field', () => {
    renderTag([], onChange);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Adding tags via Enter
  // -------------------------------------------------------------------------

  it('calls onChange with new tag when Enter is pressed', async () => {
    const user = userEvent.setup();
    renderTag(['existing'], onChange);

    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'newTag');
    await user.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining(['newTag', 'existing'])
    );
  });

  it('calls onChange with new tag when comma delimiter is typed', async () => {
    const user = userEvent.setup();
    renderTag([], onChange);

    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'hello,');

    expect(onChange).toHaveBeenCalledWith(expect.arrayContaining(['hello']));
  });

  // -------------------------------------------------------------------------
  // Paste to split
  // -------------------------------------------------------------------------

  it('splits pasted text by comma and adds multiple tags', () => {
    // Use explicit delimiters to avoid the default [',', 'Enter'] regex matching
    // individual chars in 'Enter' (n, t, e, r) which would corrupt tag values.
    renderTag([], onChange, { delimiters: [','] });

    const input = screen.getByRole('combobox');
    fireEvent.paste(input, {
      clipboardData: { getData: () => 'foo,bar,baz' },
    });

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining(['foo', 'bar', 'baz'])
    );
  });

  // -------------------------------------------------------------------------
  // Deleting chips via Backspace
  // -------------------------------------------------------------------------

  it('removes the last tag when Backspace is pressed with empty input', async () => {
    const user = userEvent.setup();
    renderTag(['first', 'second'], onChange);

    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.keyboard('{Backspace}');

    expect(onChange).toHaveBeenCalledWith(['first']);
  });

  // -------------------------------------------------------------------------
  // Unique constraint
  // -------------------------------------------------------------------------

  it('does not add a duplicate tag when uniqueTags=true', async () => {
    const user = userEvent.setup();
    renderTag(['existing'], onChange, { uniqueTags: true });

    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'existing');
    await user.keyboard('{Enter}');

    // onChange should not be called (or called with same set)
    if (onChange.mock.calls.length > 0) {
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
      const uniqueTags = new Set(lastCall);
      expect(uniqueTags.size).toBe(lastCall.length);
    }
  });

  // -------------------------------------------------------------------------
  // maxTags
  // -------------------------------------------------------------------------

  it('does not add more tags than maxTags allows', async () => {
    const user = userEvent.setup();
    renderTag(['a', 'b'], onChange, { maxTags: 2 });

    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'c');
    await user.keyboard('{Enter}');

    // With maxTags=2 and 2 existing tags, no new tag should be added
    if (onChange.mock.calls.length > 0) {
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
      expect(lastCall.length).toBeLessThanOrEqual(2);
    }
  });

  // -------------------------------------------------------------------------
  // Disabled
  // -------------------------------------------------------------------------

  it('disables the input when disabled=true', () => {
    renderTag(['a'], onChange, { disabled: true });
    expect(screen.getByRole('combobox')).toBeDisabled();
  });
});
