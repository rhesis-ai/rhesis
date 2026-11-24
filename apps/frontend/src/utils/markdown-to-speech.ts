/** Markdown as a screen reader should hear it: no symbols, links as their text. */
export function markdownToSpeech(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, ' (code block) ')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[`*_#>|~]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}
