import { rem, scaledPx } from '../theme-constants';

describe('rem', () => {
  it('turns a px size into rem against a 16px base', () => {
    expect(rem(16)).toBe('1rem');
    expect(rem(14)).toBe('0.875rem');
    expect(rem(25)).toBe('1.5625rem');
  });
});

describe('scaledPx', () => {
  afterEach(() => {
    document.documentElement.style.fontSize = '';
  });

  it('keeps the size at the default browser font size', () => {
    document.documentElement.style.fontSize = '16px';
    expect(scaledPx(13)).toBe(13);
  });

  it('grows with a larger browser font size', () => {
    document.documentElement.style.fontSize = '24px';
    expect(scaledPx(13)).toBe(19.5);
  });
});
