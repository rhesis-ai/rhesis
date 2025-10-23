/**
 * Constants for knowledge/sources related functionality
 */

// File size constants
export const FILE_SIZE_CONSTANTS = {
  MAX_UPLOAD_SIZE: 5 * 1024 * 1024, // 5MB in bytes
  BYTES_PER_KB: 1024,
} as const;

// Text truncation constants
export const TEXT_CONSTANTS = {
  DESCRIPTION_TRUNCATE_LENGTH: 50,
  FILENAME_TRUNCATE_LENGTH: 50,
  ELLIPSIS_LENGTH: 3, // Length of "..."
} as const;

// File type constants
export const FILE_TYPE_CONSTANTS = {
  ACCEPTED_EXTENSIONS:
    '.txt,.md,.pdf,.doc,.docx,.json,.csv,.xml,.epub,.pptx,.xlsx,.html,.htm,.zip',
  SIZE_UNITS: ['Bytes', 'KB', 'MB', 'GB'],
} as const;
