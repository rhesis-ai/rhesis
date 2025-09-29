/**
 * Joins URL parts together, ensuring exactly one slash between them
 * @param parts URL parts to join
 * @returns Properly formatted URL
 */
export function joinUrl(...parts: string[]): string {
  return parts
    .map(part => part.trim().replace(/^\/+|\/+$/g, '')) // Remove leading/trailing slashes
    .filter(part => part.length > 0) // Remove empty parts
    .join('/');
}
