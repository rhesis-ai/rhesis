import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import EndpointCaptures, {
  hasToolCallMapping,
  supportsMultiTurn,
} from '../EndpointCaptures';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';

const endpoint = (fields: Partial<Endpoint>) => fields as Endpoint;

describe('EndpointCaptures', () => {
  it('shows every capture as available', () => {
    render(
      <EndpointCaptures
        endpoint={endpoint({
          disable_tracing: false,
          response_mapping: {
            output: '$.text',
            tool_calls: '$.tools',
            session_id: '$.session',
            context: '$.sources',
          },
        })}
      />
    );
    expect(screen.getByLabelText('Tracing: yes')).toBeInTheDocument();
    expect(screen.getByLabelText('Tool calls: yes')).toBeInTheDocument();
    expect(screen.getByLabelText('Multi-turn: yes')).toBeInTheDocument();
    expect(screen.getByLabelText('Context: yes')).toBeInTheDocument();
  });

  it('shows every capture as missing', () => {
    render(
      <EndpointCaptures
        endpoint={endpoint({
          disable_tracing: true,
          response_mapping: { output: '$.text' },
        })}
      />
    );
    expect(screen.getByLabelText('Tracing: no')).toBeInTheDocument();
    expect(screen.getByLabelText('Tool calls: no')).toBeInTheDocument();
    expect(screen.getByLabelText('Multi-turn: no')).toBeInTheDocument();
    expect(screen.getByLabelText('Context: no')).toBeInTheDocument();
  });

  it('ignores an empty tool_calls path', () => {
    expect(
      hasToolCallMapping(endpoint({ response_mapping: { tool_calls: ' ' } }))
    ).toBe(false);
    expect(hasToolCallMapping(endpoint({}))).toBe(false);
  });

  it('counts message history in the request as multi-turn', () => {
    expect(
      supportsMultiTurn(
        endpoint({
          request_mapping: { history: '{{ messages | tojson }}' },
        })
      )
    ).toBe(true);
    expect(
      supportsMultiTurn(endpoint({ request_mapping: { q: '{{ input }}' } }))
    ).toBe(false);
  });
});
