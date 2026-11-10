import { DEFAULT_AUTHENTICATED_PATH } from '@/constants/paths';
import { safeReturnTo } from '../return-to';

describe('safeReturnTo', () => {
  it.each([
    ['javascript: scheme', 'javascript:alert(document.domain)'],
    ['mixed-case javascript: scheme', 'JaVaScRiPt:alert(1)'],
    ['javascript: after leading space', ' javascript:alert(1)'],
    ['data: scheme', 'data:text/html,<script>alert(1)</script>'],
    ['vbscript: scheme', 'vbscript:msgbox(1)'],
    ['absolute https URL', 'https://evil.example/path'],
    ['absolute http URL', 'http://evil.example'],
    ['scheme with single slash', 'http:/evil.example'],
    ['protocol-relative URL', '//evil.example'],
    ['triple slash', '///evil.example'],
    ['slash-backslash host', '/\\evil.example'],
    ['slash-backslash-slash host', '/\\/evil.example'],
    ['double backslash host', '\\\\evil.example'],
    ['backslash later in path', '/foo\\bar'],
    ['tab between slashes', '/\t/evil.example'],
    ['newline between slashes', '/\n/evil.example'],
    ['carriage return between slashes', '/\r/evil.example'],
    ['null byte', '/\u0000/evil.example'],
    ['DEL character', '/\u007F'],
    ['leading space then protocol-relative', ' //evil.example'],
    ['bare host', 'evil.example'],
    ['relative path without slash', 'architect'],
    ['empty string', ''],
    ['null', null],
    ['undefined', undefined],
  ])('rejects %s', (_label, value) => {
    expect(safeReturnTo(value)).toBe(DEFAULT_AUTHENTICATED_PATH);
  });

  it.each([
    ['/', '/'],
    ['/architect', '/architect'],
    ['/tests/123', '/tests/123'],
    ['/tests?tab=runs&page=2', '/tests?tab=runs&page=2'],
    ['/tests#section', '/tests#section'],
    ['/projects/a:b', '/projects/a:b'],
    ['/%2F%2Fevil.example', '/%2F%2Fevil.example'],
  ])('accepts same-origin path %s', (value, expected) => {
    expect(safeReturnTo(value)).toBe(expected);
  });

  it('uses the given fallback when rejecting', () => {
    expect(safeReturnTo('//evil.example', '/')).toBe('/');
  });
});
