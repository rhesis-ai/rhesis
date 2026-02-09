/**
 * Validation utilities for common form validation needs
 */

export interface ValidationResult {
  isValid: boolean;
  message?: string;
}

/**
 * Email validation using a comprehensive regex pattern
 */
export const validateEmail = (email: string): ValidationResult => {
  if (!email.trim()) {
    return { isValid: false, message: 'Email is required' };
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const isValid = emailRegex.test(email.trim());

  return {
    isValid,
    message: isValid ? undefined : 'Please enter a valid email address',
  };
};

/**
 * URL validation that accepts various formats
 * - Full URLs with protocol (https://example.com)
 * - Domain-only URLs (example.com)
 * - Subdomains (www.example.com)
 */
export const validateUrl = (
  url: string,
  options: { required?: boolean } = {}
): ValidationResult => {
  const trimmedUrl = url.trim();

  // Handle empty URLs
  if (!trimmedUrl) {
    if (options.required) {
      return { isValid: false, message: 'URL is required' };
    }
    return { isValid: true }; // Empty is valid for optional fields
  }

  // Helper function to validate domain format
  const isValidDomain = (hostname: string): boolean => {
    // Domain must have at least one dot and a valid TLD
    if (!hostname.includes('.')) return false;

    // Split into parts and validate
    const parts = hostname.split('.');
    if (parts.length < 2) return false;

    // Last part should be a valid TLD (2-6 characters, letters only)
    const tld = parts[parts.length - 1];
    if (!/^[a-zA-Z]{2,6}$/.test(tld)) return false;

    // Each part should be valid (alphanumeric + hyphens, not starting/ending with hyphen)
    return parts.every(part => {
      if (!part || part.length > 63) return false;
      if (part.startsWith('-') || part.endsWith('-')) return false;
      return /^[a-zA-Z0-9-]+$/.test(part);
    });
  };

  // Try to parse as-is first
  try {
    const urlObj = new URL(trimmedUrl);
    const isValidProtocol =
      urlObj.protocol === 'http:' || urlObj.protocol === 'https:';

    if (!isValidProtocol) {
      return {
        isValid: false,
        message: 'URL must use http:// or https:// protocol',
      };
    }

    // Validate the domain even if URL constructor succeeded
    if (!isValidDomain(urlObj.hostname)) {
      return {
        isValid: false,
        message: 'Please enter a valid domain (e.g., example.com)',
      };
    }

    return { isValid: true };
  } catch {
    // If URL constructor fails, try adding https:// prefix
    try {
      const urlWithProtocol = new URL(`https://${trimmedUrl}`);

      // Check if it's a valid domain format
      if (!isValidDomain(urlWithProtocol.hostname)) {
        return {
          isValid: false,
          message:
            'Please enter a valid URL (e.g., https://example.com or example.com)',
        };
      }

      return { isValid: true };
    } catch {
      return {
        isValid: false,
        message:
          'Please enter a valid URL (e.g., https://example.com or example.com)',
      };
    }
  }
};

/**
 * Normalize URL by adding https:// if missing
 */
export const normalizeUrl = (url: string): string => {
  if (!url.trim()) return url;

  const trimmedUrl = url.trim();

  // If it already has a protocol, return as-is
  if (trimmedUrl.startsWith('http://') || trimmedUrl.startsWith('https://')) {
    return trimmedUrl;
  }

  // Add https:// prefix for domain-only URLs
  return `https://${trimmedUrl}`;
};

/**
 * Required field validation
 */
export const validateRequired = (
  value: string,
  fieldName: string = 'Field'
): ValidationResult => {
  const isValid = Boolean(value?.trim());
  return {
    isValid,
    message: isValid ? undefined : `${fieldName} is required`,
  };
};

/**
 * Name validation (letters, spaces, hyphens, apostrophes)
 */
export const validateName = (
  name: string,
  fieldName: string = 'Name'
): ValidationResult => {
  if (!name.trim()) {
    return { isValid: false, message: `${fieldName} is required` };
  }

  const nameRegex = /^[a-zA-Z\s'-]+$/;
  const isValid = nameRegex.test(name.trim());

  return {
    isValid,
    message: isValid
      ? undefined
      : `${fieldName} can only contain letters, spaces, hyphens, and apostrophes`,
  };
};

/**
 * Organization name validation (more permissive than personal names)
 */
export const validateOrganizationName = (name: string): ValidationResult => {
  if (!name.trim()) {
    return { isValid: false, message: 'Organization name is required' };
  }

  // Allow letters, numbers, spaces, and common business punctuation
  const orgNameRegex = /^[a-zA-Z0-9\s'.-]+$/;
  const isValid = orgNameRegex.test(name.trim()) && name.trim().length >= 2;

  return {
    isValid,
    message: isValid
      ? undefined
      : 'Organization name must be at least 2 characters and contain only letters, numbers, spaces, and basic punctuation',
  };
};

/**
 * Phone number validation (basic international format)
 */
export const validatePhone = (
  phone: string,
  options: { required?: boolean } = {}
): ValidationResult => {
  const trimmedPhone = phone.trim();

  if (!trimmedPhone) {
    if (options.required) {
      return { isValid: false, message: 'Phone number is required' };
    }
    return { isValid: true };
  }

  // Basic international phone regex (allows +, digits, spaces, hyphens, parentheses)
  const phoneRegex = /^\+?[\d\s\-\(\)]{7,20}$/;
  const isValid = phoneRegex.test(trimmedPhone);

  return {
    isValid,
    message: isValid ? undefined : 'Please enter a valid phone number',
  };
};

/** Password policy from backend (min/max length, NIST-aligned). */
export interface PasswordPolicy {
  min_length: number;
  max_length: number;
}

/** Default policy when backend policy is not yet loaded. */
export const DEFAULT_PASSWORD_POLICY: PasswordPolicy = {
  min_length: 8,
  max_length: 128,
};

/**
 * Password validation (NIST-aligned: length only, no complexity rules).
 * Accepts policy from backend; uses default if not provided.
 */
export const validatePassword = (
  password: string,
  policy: PasswordPolicy = DEFAULT_PASSWORD_POLICY
): ValidationResult => {
  if (!password) {
    return { isValid: false, message: 'Password is required' };
  }

  if (password.length < policy.min_length) {
    return {
      isValid: false,
      message: `Password must be at least ${policy.min_length} characters`,
    };
  }

  if (password.length > policy.max_length) {
    return {
      isValid: false,
      message: `Password must be at most ${policy.max_length} characters`,
    };
  }

  return { isValid: true };
};

/**
 * Confirm password validation
 */
export const validatePasswordConfirmation = (
  password: string,
  confirmPassword: string
): ValidationResult => {
  if (!confirmPassword) {
    return { isValid: false, message: 'Please confirm your password' };
  }

  const isValid = password === confirmPassword;
  return {
    isValid,
    message: isValid ? undefined : 'Passwords do not match',
  };
};

/**
 * Generic length validation
 */
export const validateLength = (
  value: string,
  min: number,
  max?: number,
  fieldName: string = 'Field'
): ValidationResult => {
  const length = value.trim().length;

  if (length < min) {
    return {
      isValid: false,
      message: `${fieldName} must be at least ${min} characters long`,
    };
  }

  if (max && length > max) {
    return {
      isValid: false,
      message: `${fieldName} must be no more than ${max} characters long`,
    };
  }

  return { isValid: true };
};

/**
 * Utility to validate multiple fields at once
 */
export const validateFields = (
  validations: Record<string, ValidationResult>
): {
  isValid: boolean;
  errors: Record<string, string>;
} => {
  const errors: Record<string, string> = {};
  let isValid = true;

  Object.entries(validations).forEach(([field, result]) => {
    if (!result.isValid && result.message) {
      errors[field] = result.message;
      isValid = false;
    }
  });

  return { isValid, errors };
};
