const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Plain module (no 'use client') so both server pages and client components can call it.
export function isValidEndpointId(identifier: string): boolean {
  return !!identifier && UUID_REGEX.test(identifier);
}
