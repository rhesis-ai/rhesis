import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { LiveAnnouncerProvider, useAnnounce } from '../LiveAnnouncer';

function Announcer({ message }: { message: string }) {
  const announce = useAnnounce();
  return (
    <>
      <button onClick={() => announce(message)}>polite</button>
      <button onClick={() => announce(message, 'assertive')}>assertive</button>
    </>
  );
}

describe('LiveAnnouncer', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('puts messages into a live region that exists before they arrive', () => {
    render(
      <LiveAnnouncerProvider>
        <Announcer message="Test set deleted" />
      </LiveAnnouncerProvider>
    );
    const region = screen.getByRole('status');
    expect(region).toBeEmptyDOMElement();

    act(() => screen.getByText('polite').click());
    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(region).toHaveTextContent('Test set deleted');
  });

  it('clears the region first, so the same message is read again', () => {
    render(
      <LiveAnnouncerProvider>
        <Announcer message="Saved" />
      </LiveAnnouncerProvider>
    );
    act(() => screen.getByText('polite').click());
    act(() => {
      jest.advanceTimersByTime(200);
    });
    act(() => screen.getByText('polite').click());

    expect(screen.getByRole('status')).toBeEmptyDOMElement();
    act(() => {
      jest.advanceTimersByTime(200);
    });
    expect(screen.getByRole('status')).toHaveTextContent('Saved');
  });

  it('uses the assertive region for urgent messages', () => {
    const { container } = render(
      <LiveAnnouncerProvider>
        <Announcer message="Save failed" />
      </LiveAnnouncerProvider>
    );
    act(() => screen.getByText('assertive').click());
    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(
      container.querySelector('[aria-live="assertive"]')
    ).toHaveTextContent('Save failed');
    expect(screen.getByRole('status')).toBeEmptyDOMElement();
  });

  it('does nothing outside the provider', () => {
    render(<Announcer message="x" />);
    expect(() => screen.getByText('polite').click()).not.toThrow();
  });
});
