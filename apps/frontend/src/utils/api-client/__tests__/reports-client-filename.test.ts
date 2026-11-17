import { pdfFilename } from '../reports-client';

describe('pdfFilename', () => {
  it('prefers the UTF-8 name', () => {
    expect(
      pdfFilename(
        'attachment; filename="____-2.5.pdf"; filename*=UTF-8\'\'%E5%8F%91%E5%B8%83-2.5.pdf'
      )
    ).toBe('发布-2.5.pdf');
  });

  it('falls back to the plain name, then to report.pdf', () => {
    expect(pdfFilename('attachment; filename="Release-2.5.pdf"')).toBe(
      'Release-2.5.pdf'
    );
    expect(pdfFilename(null)).toBe('report.pdf');
  });
});
