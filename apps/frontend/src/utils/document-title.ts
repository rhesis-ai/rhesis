/**
 * Title for a detail page: `<item name> · <Section>`, or just the section
 * while the item is still loading.
 */
export function detailPageTitle(
  name: string | null | undefined,
  section: string
): string {
  const trimmed = name?.trim();
  return trimmed ? `${trimmed} · ${section}` : section;
}
