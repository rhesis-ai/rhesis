export function formatConfigSource(value: string): string {
  return value.replace(/_/g, ' ');
}

export function formatEnvironment(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export const detailGridSpacing = {
  columnSpacing: (isEditing: boolean) => (isEditing ? 2 : '30px'),
  rowSpacing: (isEditing: boolean) => (isEditing ? 2 : '50px'),
} as const;
