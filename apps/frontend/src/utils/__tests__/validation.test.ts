import {
  validateEmail,
  validateUrl,
  normalizeUrl,
  validateRequired,
  validateName,
  validateOrganizationName,
  validatePhone,
  validatePassword,
  validatePasswordConfirmation,
  validateLength,
  validateFields,
  DEFAULT_PASSWORD_POLICY,
} from '../validation';

describe('validateEmail', () => {
  it('accepts valid emails', () => {
    expect(validateEmail('user@example.com').isValid).toBe(true);
    expect(validateEmail('user+tag@example.co.uk').isValid).toBe(true);
  });

  it('rejects empty input', () => {
    const result = validateEmail('');
    expect(result.isValid).toBe(false);
    expect(result.message).toBe('Email is required');
  });

  it('rejects whitespace-only input', () => {
    expect(validateEmail('   ').isValid).toBe(false);
  });

  it('rejects invalid emails', () => {
    expect(validateEmail('not-an-email').isValid).toBe(false);
    expect(validateEmail('@missing-local.com').isValid).toBe(false);
    expect(validateEmail('missing@.com').isValid).toBe(false);
  });

  it('trims whitespace before validating', () => {
    expect(validateEmail('  user@example.com  ').isValid).toBe(true);
  });
});

describe('validateUrl', () => {
  it('accepts valid URLs with protocol', () => {
    expect(validateUrl('https://example.com').isValid).toBe(true);
    expect(validateUrl('http://example.com').isValid).toBe(true);
    expect(validateUrl('https://sub.example.com/path').isValid).toBe(true);
  });

  it('accepts valid domain-only URLs (no protocol)', () => {
    expect(validateUrl('example.com').isValid).toBe(true);
    expect(validateUrl('www.example.com').isValid).toBe(true);
  });

  it('rejects invalid protocols', () => {
    expect(validateUrl('ftp://example.com').isValid).toBe(false);
  });

  it('handles empty input based on required option', () => {
    expect(validateUrl('').isValid).toBe(true);
    expect(validateUrl('', { required: true }).isValid).toBe(false);
  });

  it('rejects invalid domains', () => {
    expect(validateUrl('https://invalid').isValid).toBe(false);
    expect(validateUrl('not a url at all!').isValid).toBe(false);
  });
});

describe('normalizeUrl', () => {
  it('adds https:// prefix to bare domains', () => {
    expect(normalizeUrl('example.com')).toBe('https://example.com');
  });

  it('preserves existing https:// protocol', () => {
    expect(normalizeUrl('https://example.com')).toBe('https://example.com');
  });

  it('preserves existing http:// protocol', () => {
    expect(normalizeUrl('http://example.com')).toBe('http://example.com');
  });

  it('returns empty/whitespace input as-is', () => {
    expect(normalizeUrl('')).toBe('');
    expect(normalizeUrl('   ')).toBe('   ');
  });

  it('trims whitespace', () => {
    expect(normalizeUrl('  example.com  ')).toBe('https://example.com');
  });
});

describe('validateRequired', () => {
  it('accepts non-empty values', () => {
    expect(validateRequired('hello').isValid).toBe(true);
  });

  it('rejects empty string', () => {
    const result = validateRequired('', 'Name');
    expect(result.isValid).toBe(false);
    expect(result.message).toBe('Name is required');
  });

  it('rejects whitespace-only', () => {
    expect(validateRequired('   ').isValid).toBe(false);
  });

  it('uses default field name', () => {
    const result = validateRequired('');
    expect(result.message).toBe('Field is required');
  });
});

describe('validateName', () => {
  it('accepts valid names', () => {
    expect(validateName('John Doe').isValid).toBe(true);
    expect(validateName("O'Brien").isValid).toBe(true);
    expect(validateName('Mary-Jane').isValid).toBe(true);
  });

  it('rejects empty names', () => {
    expect(validateName('').isValid).toBe(false);
  });

  it('rejects names with numbers or special chars', () => {
    expect(validateName('John123').isValid).toBe(false);
    expect(validateName('user@name').isValid).toBe(false);
  });

  it('uses custom field name in error message', () => {
    const result = validateName('', 'First name');
    expect(result.message).toBe('First name is required');
  });
});

describe('validateOrganizationName', () => {
  it('accepts valid organization names', () => {
    expect(validateOrganizationName('Acme Corp').isValid).toBe(true);
    expect(validateOrganizationName('Company 123').isValid).toBe(true);
    expect(validateOrganizationName("O'Reilly Media").isValid).toBe(true);
  });

  it('rejects empty names', () => {
    expect(validateOrganizationName('').isValid).toBe(false);
  });

  it('rejects single-character names', () => {
    expect(validateOrganizationName('A').isValid).toBe(false);
  });

  it('rejects names with special characters', () => {
    expect(validateOrganizationName('Co@mp').isValid).toBe(false);
  });
});

describe('validatePhone', () => {
  it('accepts valid phone numbers', () => {
    expect(validatePhone('+1 555-123-4567').isValid).toBe(true);
    expect(validatePhone('(555) 123-4567').isValid).toBe(true);
    expect(validatePhone('5551234567').isValid).toBe(true);
  });

  it('handles empty input based on required option', () => {
    expect(validatePhone('').isValid).toBe(true);
    expect(validatePhone('', { required: true }).isValid).toBe(false);
  });

  it('rejects too-short numbers', () => {
    expect(validatePhone('123').isValid).toBe(false);
  });
});

describe('validatePassword', () => {
  it('accepts valid passwords', () => {
    expect(validatePassword('password123').isValid).toBe(true);
    expect(validatePassword('12345678').isValid).toBe(true);
  });

  it('rejects empty passwords', () => {
    const result = validatePassword('');
    expect(result.isValid).toBe(false);
    expect(result.message).toBe('Password is required');
  });

  it('rejects passwords shorter than minimum length', () => {
    const result = validatePassword('short');
    expect(result.isValid).toBe(false);
    expect(result.message).toContain('at least');
  });

  it('rejects passwords exceeding max length', () => {
    const longPassword = 'a'.repeat(129);
    const result = validatePassword(longPassword);
    expect(result.isValid).toBe(false);
    expect(result.message).toContain('at most');
  });

  it('respects custom policy', () => {
    const policy = { min_length: 12, max_length: 64 };
    expect(validatePassword('short123', policy).isValid).toBe(false);
    expect(validatePassword('longenough12', policy).isValid).toBe(true);
  });

  it('has correct default policy', () => {
    expect(DEFAULT_PASSWORD_POLICY.min_length).toBe(8);
    expect(DEFAULT_PASSWORD_POLICY.max_length).toBe(128);
  });
});

describe('validatePasswordConfirmation', () => {
  it('accepts matching passwords', () => {
    expect(validatePasswordConfirmation('password', 'password').isValid).toBe(
      true
    );
  });

  it('rejects mismatched passwords', () => {
    const result = validatePasswordConfirmation('password', 'different');
    expect(result.isValid).toBe(false);
    expect(result.message).toBe('Passwords do not match');
  });

  it('rejects empty confirmation', () => {
    const result = validatePasswordConfirmation('password', '');
    expect(result.isValid).toBe(false);
    expect(result.message).toBe('Please confirm your password');
  });
});

describe('validateLength', () => {
  it('accepts values within range', () => {
    expect(validateLength('hello', 1, 10).isValid).toBe(true);
  });

  it('rejects values below minimum', () => {
    const result = validateLength('hi', 5, 10, 'Title');
    expect(result.isValid).toBe(false);
    expect(result.message).toContain('at least 5');
  });

  it('rejects values above maximum', () => {
    const result = validateLength('a very long string', 1, 5, 'Title');
    expect(result.isValid).toBe(false);
    expect(result.message).toContain('no more than 5');
  });

  it('works without max', () => {
    expect(validateLength('hello', 1).isValid).toBe(true);
  });

  it('trims whitespace before checking length', () => {
    expect(validateLength('  hi  ', 5).isValid).toBe(false);
  });
});

describe('validateFields', () => {
  it('returns valid when all fields pass', () => {
    const result = validateFields({
      email: { isValid: true },
      name: { isValid: true },
    });
    expect(result.isValid).toBe(true);
    expect(result.errors).toEqual({});
  });

  it('collects all errors', () => {
    const result = validateFields({
      email: { isValid: false, message: 'Email is required' },
      name: { isValid: false, message: 'Name is required' },
    });
    expect(result.isValid).toBe(false);
    expect(result.errors).toEqual({
      email: 'Email is required',
      name: 'Name is required',
    });
  });

  it('returns only failed fields', () => {
    const result = validateFields({
      email: { isValid: true },
      name: { isValid: false, message: 'Name is required' },
    });
    expect(result.isValid).toBe(false);
    expect(Object.keys(result.errors)).toEqual(['name']);
  });
});
