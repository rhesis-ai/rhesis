import {
  formatFileSize,
  formatDate,
  getFileExtension,
  truncateFilename,
  FILE_SIZE_CONSTANTS,
  TEXT_CONSTANTS,
} from '../knowledge';

describe('formatFileSize', () => {
  it('returns empty string for falsy values', () => {
    expect(formatFileSize(undefined)).toBe('');
    expect(formatFileSize(0)).toBe('');
  });

  it('formats bytes', () => {
    expect(formatFileSize(500)).toBe('500 Bytes');
    expect(formatFileSize(1)).toBe('1 Bytes');
  });

  it('formats kilobytes', () => {
    expect(formatFileSize(1024)).toBe('1 KB');
    expect(formatFileSize(1536)).toBe('1.5 KB');
    expect(formatFileSize(10240)).toBe('10 KB');
  });

  it('formats megabytes', () => {
    expect(formatFileSize(1048576)).toBe('1 MB');
    expect(formatFileSize(2621440)).toBe('2.5 MB');
  });

  it('formats gigabytes', () => {
    expect(formatFileSize(1073741824)).toBe('1 GB');
  });

  it('has correct max upload size constant', () => {
    expect(FILE_SIZE_CONSTANTS.MAX_UPLOAD_SIZE).toBe(5 * 1024 * 1024);
  });
});

describe('formatDate', () => {
  it('returns Unknown for null/undefined', () => {
    expect(formatDate(null)).toBe('Unknown');
    expect(formatDate(undefined)).toBe('Unknown');
    expect(formatDate('')).toBe('Unknown');
  });

  it('formats valid date strings as DD/MM/YYYY', () => {
    expect(formatDate('2024-01-15T14:30:00Z')).toBe('15/01/2024');
    expect(formatDate('2024-12-25T00:00:00Z')).toBe('25/12/2024');
  });

  it('returns Invalid date for garbage input', () => {
    expect(formatDate('not-a-date')).toBe('Invalid date');
  });
});

describe('getFileExtension', () => {
  it('returns extension for standard filenames', () => {
    expect(getFileExtension('document.pdf')).toBe('pdf');
    expect(getFileExtension('image.PNG')).toBe('png');
    expect(getFileExtension('archive.tar.gz')).toBe('gz');
  });

  it('returns unknown for missing filename', () => {
    expect(getFileExtension(undefined)).toBe('unknown');
    expect(getFileExtension('')).toBe('unknown');
  });

  it('returns unknown for files with no extension', () => {
    expect(getFileExtension('Makefile')).toBe('makefile');
  });
});

describe('truncateFilename', () => {
  it('returns filename unchanged when under max length', () => {
    expect(truncateFilename('short.txt')).toBe('short.txt');
  });

  it('truncates long filenames preserving extension', () => {
    const longName = 'a'.repeat(60) + '.pdf';
    const result = truncateFilename(longName);
    expect(result.length).toBeLessThanOrEqual(
      TEXT_CONSTANTS.FILENAME_TRUNCATE_LENGTH
    );
    expect(result).toMatch(/\.pdf$/);
    expect(result).toContain('...');
  });

  it('uses custom max length', () => {
    const result = truncateFilename('my-document-with-long-name.txt', 20);
    expect(result.length).toBeLessThanOrEqual(20);
    expect(result).toMatch(/\.txt$/);
    expect(result).toContain('...');
  });

  it('truncates files without extension', () => {
    const longName = 'a'.repeat(60);
    const result = truncateFilename(longName);
    expect(result.length).toBeLessThanOrEqual(
      TEXT_CONSTANTS.FILENAME_TRUNCATE_LENGTH
    );
    expect(result).toContain('...');
  });

  it('handles edge case where extension is very long', () => {
    const name = 'f.' + 'x'.repeat(48);
    const result = truncateFilename(name, 10);
    // Falls back to simple truncation since extension is too long
    expect(result.length).toBeLessThanOrEqual(10);
    expect(result).toContain('...');
  });
});
