import { getApiKeyFieldHint } from '../model-providers';

describe('getApiKeyFieldHint', () => {
  it('tells Vertex AI users the field takes a service-account JSON key', () => {
    expect(getApiKeyFieldHint('vertex_ai')).toMatch(/service-account JSON/);
  });

  it('leaves providers that take a plain API key on the default hint', () => {
    expect(getApiKeyFieldHint('openai')).toBeUndefined();
    expect(getApiKeyFieldHint(undefined)).toBeUndefined();
  });
});
