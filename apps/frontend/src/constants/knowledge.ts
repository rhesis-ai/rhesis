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
    '.txt,.md,.pdf,.docx,.json,.csv,.xml,.epub,.pptx,.xlsx,.html,.htm,.zip',
  SIZE_UNITS: ['Bytes', 'KB', 'MB', 'GB'],
} as const;

// Utility functions
export const formatFileSize = (bytes?: number): string => {
  if (!bytes) return 'Unknown';

  const sizes = FILE_TYPE_CONSTANTS.SIZE_UNITS;
  const i = Math.floor(
    Math.log(bytes) / Math.log(FILE_SIZE_CONSTANTS.BYTES_PER_KB)
  );
  return `${Math.round((bytes / Math.pow(FILE_SIZE_CONSTANTS.BYTES_PER_KB, i)) * 100) / 100} ${sizes[i]}`;
};

export const formatDate = (dateString: string | null | undefined): string => {
  if (!dateString) return 'Unknown';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'Invalid date';

    // Use consistent DD/MM/YYYY formatting
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');

    return `${day}/${month}/${year}`;
  } catch {
    return 'Invalid date';
  }
};

export const getFileExtension = (filename?: string): string => {
  if (!filename) return 'unknown';
  const ext = filename.split('.').pop()?.toLowerCase();
  return ext || 'unknown';
};

export const truncateFilename = (
  filename: string,
  maxLength: number = TEXT_CONSTANTS.FILENAME_TRUNCATE_LENGTH
): string => {
  if (filename.length <= maxLength) return filename;

  // Try to preserve the file extension
  const lastDotIndex = filename.lastIndexOf('.');
  if (lastDotIndex > 0) {
    const extension = filename.substring(lastDotIndex);
    const nameWithoutExt = filename.substring(0, lastDotIndex);
    const availableLength =
      maxLength - extension.length - TEXT_CONSTANTS.ELLIPSIS_LENGTH;

    if (availableLength > 0) {
      return `${nameWithoutExt.substring(0, availableLength)}...${extension}`;
    }
  }

  // Fallback: just truncate and add ellipsis
  return `${filename.substring(0, maxLength - TEXT_CONSTANTS.ELLIPSIS_LENGTH)}...`;
};
