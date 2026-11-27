import { sectionEditButtonSx } from '../SectionCardActions';

describe('sectionEditButtonSx', () => {
  it('leaves the hover fill and label colour to the theme, together', () => {
    // Overriding only one of the two left the theme's light label on a pale fill.
    const hover = sectionEditButtonSx['&:hover'] as Record<string, unknown>;
    const setsFill = 'bgcolor' in hover || 'backgroundColor' in hover;
    expect(setsFill).toBe('color' in hover);
  });
});
