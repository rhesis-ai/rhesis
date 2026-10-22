import {
  buildRequestTemplate,
  parseRequestTemplate,
} from '../requestTemplateRows';
import {
  headerRowsToJson,
  parseHeaderRows,
  syncAuthorizationHeader,
} from '../headerRows';
import { mappingTarget, responsePaths } from '../responsePaths';

describe('request template rows', () => {
  it('reads a flat template and keeps its filters', () => {
    const rows = parseRequestTemplate(
      '{"q": "{{ input }}", "history": "{{ messages | to_anthropic_messages | tojson }}", "system_prompt": "Be brief."}'
    );
    expect(rows).toEqual({
      fields: {
        input: { field: 'q', filter: '' },
        messages: {
          field: 'history',
          filter: ' | to_anthropic_messages | tojson',
        },
      },
      systemPrompt: 'Be brief.',
    });
  });

  it('reads nested objects as dotted paths', () => {
    expect(
      parseRequestTemplate('{"payload": {"query": "{{ input }}"}}')?.fields
    ).toEqual({ input: { field: 'payload.query', filter: '' } });
  });

  it.each([
    ['an array', '{"messages": [{"role": "user", "content": "{{ input }}"}]}'],
    ['a literal value', '{"model": "gpt-4o", "q": "{{ input }}"}'],
    ['a variable used twice', '{"a": "{{ input }}", "b": "{{ input }}"}'],
    ['Jinja that is not JSON', '{"q": {{ input | tojson }}}'],
  ])('leaves %s to the JSON editor', (_label, template) => {
    expect(parseRequestTemplate(template)).toBeNull();
  });

  it('round-trips, giving new rows their default filter', () => {
    const rows = parseRequestTemplate('{"q": "{{ messages }}"}');
    expect(rows).not.toBeNull();
    const built = buildRequestTemplate({
      fields: {
        ...rows?.fields,
        input: { field: 'prompt' },
        files: { field: 'attachments' },
      },
      systemPrompt: '',
    });
    expect(JSON.parse(built)).toEqual({
      prompt: '{{ input }}',
      q: '{{ messages }}',
      attachments: '{{ files | to_openai | tojson }}',
    });
  });

  it('builds nested objects and leaves out clashing paths', () => {
    const built = buildRequestTemplate({
      fields: {
        input: { field: 'payload.query' },
        conversation_id: { field: 'payload.meta.id' },
        messages: { field: 'payload.query.history' },
      },
      systemPrompt: '',
    });
    expect(JSON.parse(built)).toEqual({
      payload: { meta: { id: '{{ conversation_id }}' } },
    });
  });

  it('drops empty fields and keeps the system prompt as a plain key', () => {
    const built = buildRequestTemplate({
      fields: { input: { field: 'q' }, messages: { field: '  ' } },
      systemPrompt: 'You are helpful.',
    });
    expect(JSON.parse(built)).toEqual({
      q: '{{ input }}',
      system_prompt: 'You are helpful.',
    });
  });
});

describe('header rows', () => {
  it('turns flat headers into rows and back, skipping blank keys', () => {
    const rows = parseHeaderRows('{"Content-Type": "application/json"}');
    expect(rows?.map(r => [r.key, r.value])).toEqual([
      ['Content-Type', 'application/json'],
    ]);
    const json = headerRowsToJson([
      ...(rows ?? []),
      { id: 'x', key: ' ', value: 'ignored' },
    ]);
    expect(JSON.parse(json)).toEqual({ 'Content-Type': 'application/json' });
  });

  it('refuses headers whose values are not text', () => {
    expect(parseHeaderRows('{"X-Retry": 3}')).toBeNull();
    expect(parseHeaderRows('not json')).toBeNull();
  });

  it('adds and removes the Authorization header with the token', () => {
    const withToken = syncAuthorizationHeader('{"A": "b"}', 'sk-1');
    expect(JSON.parse(withToken)).toEqual({
      Authorization: 'Bearer {{ auth_token }}',
      A: 'b',
    });
    expect(JSON.parse(syncAuthorizationHeader(withToken, ''))).toEqual({
      A: 'b',
    });
  });

  it('leaves headers alone when one already uses the token', () => {
    const json = '{"X-Key": "{{ auth_token }}"}';
    expect(syncAuthorizationHeader(json, 'sk-1')).toBe(json);
  });
});

describe('response paths', () => {
  it('lists every key, arrays whole and through their first item', () => {
    expect(
      responsePaths({
        text: 'hi',
        choices: [{ message: { content: 'x' } }],
        tags: ['a'],
      })
    ).toEqual([
      'text',
      'choices',
      'choices[0].message',
      'choices[0].message.content',
      'tags',
    ]);
  });

  it('reads the API response out of the test result wrapper', () => {
    expect(mappingTarget({ raw_response: { a: 1 }, success: true })).toEqual({
      a: 1,
    });
    expect(mappingTarget({ a: 1 })).toEqual({ a: 1 });
  });
});
