export function deriveWebSocketUrl(backendUrl: string): string {
  const url = new URL(backendUrl);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';

  const pathname = url.pathname.replace(/\/+$/g, '');
  url.pathname = `${pathname}/ws`;
  url.search = '';
  url.hash = '';

  return url.toString();
}
