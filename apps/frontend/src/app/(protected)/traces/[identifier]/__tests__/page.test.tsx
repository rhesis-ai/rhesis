import TraceByIdPage from '../page';

const redirect = jest.fn();
const lookupSpan = jest.fn();

jest.mock('next/navigation', () => ({
  redirect: (url: string) => redirect(url),
}));

jest.mock('@/utils/require-session', () => ({
  requireSession: jest.fn().mockResolvedValue({}),
}));

jest.mock('@/utils/api-client/server-factory', () => ({
  createServerApiFactory: jest.fn().mockResolvedValue({
    getTelemetryClient: () => ({ lookupSpan }),
  }),
}));

describe('TraceByIdPage', () => {
  it('redirects to the trace with the linked span selected', async () => {
    lookupSpan.mockResolvedValue({
      trace_id: 'trace-1',
      project_id: 'project-1',
      span_id: 'span-1',
    });

    await TraceByIdPage({ params: Promise.resolve({ identifier: 'db-id' }) });

    expect(lookupSpan).toHaveBeenCalledWith('db-id');
    expect(redirect).toHaveBeenCalledWith(
      '/traces?open_trace=trace-1&project_id=project-1&open_span=span-1'
    );
  });
});
