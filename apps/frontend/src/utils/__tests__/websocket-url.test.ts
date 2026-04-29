import { deriveWebSocketUrl } from '../websocket-url';

describe('deriveWebSocketUrl', () => {
  it('converts http backend URL to ws /ws endpoint', () => {
    expect(deriveWebSocketUrl('http://localhost:8080')).toBe(
      'ws://localhost:8080/ws'
    );
  });

  it('converts https backend URL to wss /ws endpoint', () => {
    expect(deriveWebSocketUrl('https://api.rhesis.ai')).toBe(
      'wss://api.rhesis.ai/ws'
    );
  });

  it('preserves backend URL path before appending /ws', () => {
    expect(deriveWebSocketUrl('http://localhost:8080/api')).toBe(
      'ws://localhost:8080/api/ws'
    );
  });
});
