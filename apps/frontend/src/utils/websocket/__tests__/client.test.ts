import { WebSocketClient } from '../client';
import { EventType, type WebSocketMessage } from '../types';
import {
  MODEL_NOT_CONFIGURED_ERROR_CODE,
  onModelNotConfigured,
} from '@/utils/model-setup';

// handleMessage is private; it is what `ws.onmessage` calls for every frame.
function deliver(client: WebSocketClient, message: WebSocketMessage) {
  (
    client as unknown as { handleMessage: (m: WebSocketMessage) => void }
  ).handleMessage(message);
}

describe('WebSocketClient model_not_configured routing', () => {
  let client: WebSocketClient;
  let listener: jest.Mock;
  let unsubscribe: () => void;

  beforeEach(() => {
    client = new WebSocketClient({ url: 'localhost/ws', token: 'test-token' });
    listener = jest.fn();
    unsubscribe = onModelNotConfigured(listener);
  });

  afterEach(() => unsubscribe());

  it('reports an Architect error with the code and still delivers it', () => {
    const handler = jest.fn();
    client.subscribe(EventType.ARCHITECT_ERROR, handler);
    const message = {
      type: EventType.ARCHITECT_ERROR,
      payload: {
        session_id: 'sess-1',
        error: 'No usable generation model is set up.',
        error_code: MODEL_NOT_CONFIGURED_ERROR_CODE,
      },
    };

    deliver(client, message);

    expect(listener).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(message);
  });

  it('reports a preflight summary with a failed model check', () => {
    deliver(client, {
      type: EventType.PREFLIGHT_COMPLETE,
      payload: {
        correlation_id: 'c1',
        summary: 'failed',
        checks: [
          {
            check_id: 'evaluation_model',
            status: 'failed',
            error_code: MODEL_NOT_CONFIGURED_ERROR_CODE,
          },
        ],
      },
    });

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('does not report other errors', () => {
    deliver(client, {
      type: EventType.ARCHITECT_ERROR,
      payload: { session_id: 'sess-1', error: 'boom', error_code: null },
    });

    expect(listener).not.toHaveBeenCalled();
  });
});
