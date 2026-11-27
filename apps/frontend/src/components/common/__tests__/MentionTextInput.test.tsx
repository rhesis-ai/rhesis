import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import MentionTextInput from '../MentionTextInput';

describe('MentionTextInput', () => {
  it('reserves its minimum rows, whatever unit the theme line height has', () => {
    render(
      <ThemeProvider theme={lightTheme}>
        <MentionTextInput
          value=""
          onChange={jest.fn()}
          placeholder="Explain your verdict"
          minRows={4}
        />
      </ThemeProvider>
    );

    // An invalid calc() is dropped, which left the field a single line high.
    const field = screen.getByPlaceholderText('Explain your verdict');
    expect(field.style.minHeight).toMatch(/^calc\(4 \* /);
    expect(field.style.minHeight).not.toMatch(/remem|pxem/);
  });
});
