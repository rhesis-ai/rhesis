/**
 * Generate a UUIDv4 that works in any browsing context.
 *
 * ``crypto.randomUUID`` is only exposed in a *secure context* (HTTPS or
 * ``localhost``). A self-hosted deployment is frequently reached over plain
 * ``http`` on a LAN IP / internal hostname, where the browser omits it and a
 * direct call throws ``crypto.randomUUID is not a function``.
 *
 * ``crypto.getRandomValues`` is NOT secure-context-gated and is a CSPRNG, so
 * we build a v4 UUID from it as the fallback. This keeps the id both portable
 * (works over http on any host) and cryptographically strong. The final
 * ``Math.random`` branch is a last resort for exotic runtimes with no Web
 * Crypto at all; it is not cryptographically secure.
 *
 * Suitable for non-sensitive identifiers (React keys, correlation/trace ids).
 * For unguessable security tokens (invites, share links, reset codes),
 * generate them server-side with a CSPRNG — do not rely on this helper.
 */
export function safeRandomUUID(): string {
  const cryptoObj = globalThis.crypto;

  if (typeof cryptoObj?.randomUUID === 'function') {
    return cryptoObj.randomUUID();
  }

  if (typeof cryptoObj?.getRandomValues === 'function') {
    const bytes = cryptoObj.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 10xx
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0'));
    return (
      `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-` +
      `${hex[4]}${hex[5]}-` +
      `${hex[6]}${hex[7]}-` +
      `${hex[8]}${hex[9]}-` +
      `${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`
    );
  }

  // Last resort only: no Web Crypto available. Not cryptographically secure.
  const rand = Math.random().toString(36).slice(2);
  return `id_${Date.now().toString(36)}_${rand}`;
}
