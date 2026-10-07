import {
  CLIENT_HEADER,
  CLIENT_IP_HEADER,
  browserIp,
  webClientHeaders,
} from '../provenance';

/**
 * The headers the Next.js server adds when it calls the backend for a browser.
 * The backend's audit log and IP rate limits read them; without the IP header
 * every UI call looks like it came from the frontend pod.
 */
describe('browserIp', () => {
  it('prefers the address the ingress set in X-Real-IP', () => {
    const headers = new Headers({
      'x-real-ip': '203.0.113.7',
      'x-forwarded-for': '198.51.100.1, 10.0.0.2',
    });
    expect(browserIp(headers)).toBe('203.0.113.7');
  });

  it('falls back to the first X-Forwarded-For entry', () => {
    const headers = new Headers({
      'x-forwarded-for': '198.51.100.1, 10.0.0.2',
    });
    expect(browserIp(headers)).toBe('198.51.100.1');
  });

  it('returns null when neither is present', () => {
    expect(browserIp(new Headers())).toBeNull();
  });
});

describe('webClientHeaders', () => {
  it('names the web client and passes the browser IP on', () => {
    const headers = webClientHeaders(
      new Headers({ 'x-real-ip': '203.0.113.7' })
    );
    expect(headers).toEqual({
      [CLIENT_HEADER]: 'web',
      [CLIENT_IP_HEADER]: '203.0.113.7',
    });
  });

  it('leaves the IP out when the browser address is unknown', () => {
    expect(webClientHeaders(new Headers())).toEqual({ [CLIENT_HEADER]: 'web' });
  });
});
