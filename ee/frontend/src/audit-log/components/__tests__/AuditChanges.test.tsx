/**
 * The drawer's Changes block: values, secrets, hidden content and job summaries.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import AuditChanges from '../AuditChanges';
import type { AuditEventDetail } from '../../types';

function makeEvent(overrides: Partial<AuditEventDetail>): AuditEventDetail {
  return {
    id: 'e1',
    organization_id: 'o1',
    project_id: null,
    occurred_at: '2026-10-05T12:00:00Z',
    recorded_at: '2026-10-05T12:00:00Z',
    action: 'endpoint.updated',
    outcome: 'success',
    status_code: null,
    actor_type: 'user',
    actor_id: 'u1',
    actor_credential_id: null,
    actor_credential_hint: null,
    actor_label: null,
    channel: 'web',
    ip: null,
    user_agent: null,
    resource_id: 'r1',
    resource_label: null,
    request_id: null,
    trace_id: 't1',
    span_id: 's1',
    job_id: null,
    changes: [],
    ...overrides,
  };
}

describe('AuditChanges', () => {
  it('shows before and after for a value change', () => {
    render(
      <AuditChanges
        event={makeEvent({
          changes: [
            { field: 'temperature', kind: 'value', before: 0.7, after: 0.2 },
          ],
        })}
      />
    );
    expect(screen.getByText('temperature')).toBeInTheDocument();
    expect(screen.getByText('0.7')).toBeInTheDocument();
    expect(screen.getByText('0.2')).toBeInTheDocument();
  });

  it('never shows values for a secret', () => {
    render(
      <AuditChanges
        event={makeEvent({
          changes: [{ field: 'auth_token', kind: 'secret' }],
        })}
      />
    );
    expect(
      screen.getByText(/Secret values are never recorded/)
    ).toBeInTheDocument();
  });

  it('hides content unless the API returns it', () => {
    const { rerender } = render(
      <AuditChanges
        event={makeEvent({ changes: [{ field: 'prompt', kind: 'content' }] })}
      />
    );
    expect(screen.getByText('Changed (content hidden)')).toBeInTheDocument();

    rerender(
      <AuditChanges
        event={makeEvent({
          changes: [{ field: 'prompt', kind: 'content' }],
          content_changes: [{ field: 'prompt', before: 'old', after: 'new' }],
        })}
      />
    );
    expect(screen.getByText('old')).toBeInTheDocument();
    expect(screen.getByText('new')).toBeInTheDocument();
  });

  it('shows a job summary as a count and ids', () => {
    render(
      <AuditChanges
        event={makeEvent({
          action: 'test.created',
          changes: { count: 2, ids: ['a', 'b'] },
        })}
      />
    );
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('a, b')).toBeInTheDocument();
  });

  it('says so when nothing changed', () => {
    render(<AuditChanges event={makeEvent({ changes: [] })} />);
    expect(screen.getByText(/No field changes/)).toBeInTheDocument();
  });
});
