export function sharedPrefix(strings: string[]): string {
  if (strings.length < 2) return '';
  let prefix = '';
  const first = strings[0];
  outer: for (let i = 0; i < first.length; i++) {
    const ch = first[i];
    for (let j = 1; j < strings.length; j++) {
      if (i >= strings[j].length || strings[j][i] !== ch) break outer;
    }
    prefix += ch;
  }
  // Cut at last space or colon so we don't trim mid-word.
  const lastBreak = Math.max(prefix.lastIndexOf(' '), prefix.lastIndexOf(':'));
  if (lastBreak >= 0) {
    prefix = prefix.slice(0, lastBreak + 1);
  } else {
    prefix = '';
  }
  if (prefix.length < 3) return '';
  return prefix;
}

export function trimSharedPrefix(names: string[]): string[] {
  const prefix = sharedPrefix(names);
  if (!prefix) return names;
  const trimmed = names.map(n => n.slice(prefix.length));
  // If trimming would make any two siblings identical, return originals.
  if (new Set(trimmed).size < trimmed.length) return names;
  return trimmed;
}
