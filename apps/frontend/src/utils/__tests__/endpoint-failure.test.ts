import { getEndpointFailure } from '../endpoint-failure';
import { TestOutput } from '@/utils/api-client/interfaces/test-results';

const SAFEGUARDING_BODY = '{"detail":"Blocked by safeguarding policy"}';

/** What the backend stores for a single-turn call the target answered with 400. */
function flatHttpFailure(): TestOutput {
  return {
    output: `HTTP 400 error from endpoint: Bad Request. Response content: ${SAFEGUARDING_BODY}`,
    error: 'HTTP 400 error from endpoint',
    error_type: 'http_error',
    status_code: 400,
    reason: 'Bad Request',
    response_content: SAFEGUARDING_BODY,
  } as TestOutput;
}

/** Penelope trace whose first target message hit a 403. */
function multiTurnFailure(): TestOutput {
  return {
    history: [
      {
        target_interaction: {
          tool_name: 'send_message_to_target',
          tool_message: {
            content: JSON.stringify({
              metadata: {
                error_details: {
                  error: true,
                  error_type: 'http_error',
                  status_code: 403,
                  message: 'HTTP 403 error from endpoint',
                  output: 'HTTP 403 error from endpoint: Forbidden',
                },
              },
            }),
          },
        },
      },
    ],
  } as TestOutput;
}

describe('getEndpointFailure', () => {
  describe('flat single-turn failures', () => {
    it('reads the status code, reason and response body', () => {
      const failure = getEndpointFailure(flatHttpFailure());

      expect(failure).not.toBeNull();
      expect(failure?.statusCode).toBe(400);
      expect(failure?.reason).toBe('Bad Request');
      expect(failure?.responseBody).toBe(SAFEGUARDING_BODY);
      expect(failure?.errorType).toBe('http_error');
    });

    it('summarises without repeating the status code', () => {
      const failure = getEndpointFailure(flatHttpFailure());

      expect(failure?.summary).toContain('400');
      expect(failure?.summary.match(/400/g)).toHaveLength(1);
    });

    it('accepts a status code sent as a string', () => {
      const failure = getEndpointFailure({
        error: 'rejected',
        error_type: 'http_error',
        status_code: '429',
      } as unknown as TestOutput);

      expect(failure?.statusCode).toBe(429);
    });

    it('falls back to response_body for rows written before the invokers were normalised', () => {
      const failure = getEndpointFailure({
        error: 'ws rejected',
        error_type: 'websocket_connection_error',
        status_code: 403,
        response_body: '{"detail":"forbidden"}',
      } as unknown as TestOutput);

      expect(failure?.responseBody).toBe('{"detail":"forbidden"}');
    });
  });

  describe('multi-turn failures', () => {
    it('reads the error nested in the first target interaction', () => {
      const failure = getEndpointFailure(multiTurnFailure());

      expect(failure).not.toBeNull();
      expect(failure?.statusCode).toBe(403);
      expect(failure?.message).toContain('Forbidden');
    });

    it('ignores turns that are not send_message_to_target', () => {
      const output = {
        history: [
          {
            target_interaction: {
              tool_name: 'some_other_tool',
              tool_message: { content: '{}' },
            },
          },
        ],
      } as TestOutput;

      expect(getEndpointFailure(output)).toBeNull();
    });

    it('survives a tool message that is not valid JSON', () => {
      const output = {
        history: [
          {
            target_interaction: {
              tool_name: 'send_message_to_target',
              tool_message: { content: 'not json at all' },
            },
          },
        ],
      } as TestOutput;

      expect(getEndpointFailure(output)).toBeNull();
    });
  });

  describe('failures carrying no HTTP status', () => {
    // SDK/connector and network failures never have one. They are still failures, and
    // treating them as answers is how their error text got scored into a verdict.
    it.each(['sdk_function_error', 'sdk_timeout', 'network_error'])(
      'detects %s',
      errorType => {
        const failure = getEndpointFailure({
          output: `failure: ${errorType}`,
          error: errorType,
          error_type: errorType,
        } as unknown as TestOutput);

        expect(failure).not.toBeNull();
        expect(failure?.statusCode).toBeUndefined();
        expect(failure?.summary).toContain('an error');
      }
    );
  });

  describe('results that did not fail', () => {
    it('returns null for a successful response', () => {
      expect(
        getEndpointFailure({ output: 'the model answered' } as TestOutput)
      ).toBeNull();
    });

    it('returns null for a target that maps its own "error" field', () => {
      // error_type is required alongside error precisely so this is not a false positive.
      expect(
        getEndpointFailure({
          output: 'an answer',
          error: 'some field the target happened to map',
        } as TestOutput)
      ).toBeNull();
    });

    it('returns null for missing output', () => {
      expect(getEndpointFailure(undefined)).toBeNull();
      expect(getEndpointFailure(null)).toBeNull();
    });
  });
});
