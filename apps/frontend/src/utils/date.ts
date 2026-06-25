export function formatDate(
  date: string | Date | undefined,
  timezone?: string
): string {
  if (!date) return 'N/A';

  const timeZone = timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return dateObj.toLocaleString('en-GB', {
    timeZone,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
