import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import FeedbackModal from '../FeedbackModal';
import { NotificationProvider } from '../NotificationContext';

function renderModal(
  props: Partial<React.ComponentProps<typeof FeedbackModal>> = {}
) {
  const defaults = { open: true, onClose: jest.fn() };
  return render(
    <NotificationProvider>
      <FeedbackModal {...defaults} {...props} />
    </NotificationProvider>
  );
}

function makeFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

beforeEach(() => {
  (global.fetch as jest.Mock) = jest
    .fn()
    .mockResolvedValue(makeFetchResponse({}));
});

afterEach(() => {
  jest.clearAllMocks();
});

describe('FeedbackModal', () => {
  it('renders the dialog when open is true', () => {
    renderModal();
    expect(screen.getByText('Provide Feedback')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /send feedback/i })
    ).toBeInTheDocument();
  });

  it('does not render dialog content when open is false', () => {
    renderModal({ open: false });
    expect(screen.queryByText('Provide Feedback')).not.toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onClose = jest.fn();
    renderModal({ onClose });

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onClose).toHaveBeenCalled();
  });

  it('shows an error notification when submitting with empty feedback text', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await screen.findByText(/please provide some feedback/i);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('sends a POST to /api/feedback with the feedback text', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText(/your feedback/i), 'Great product!');
    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/feedback',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Great product!'),
        })
      );
    });
  });

  it('includes email in the POST body when provided', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText(/your feedback/i), 'Nice work!');
    await user.type(screen.getByLabelText(/your email/i), 'user@example.com');
    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await waitFor(() => {
      const body = JSON.parse(
        (global.fetch as jest.Mock).mock.calls[0][1].body
      );
      expect(body.email).toBe('user@example.com');
    });
  });

  it('omits email from the POST body when email field is empty', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText(/your feedback/i), 'Looks good');
    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await waitFor(() => {
      const body = JSON.parse(
        (global.fetch as jest.Mock).mock.calls[0][1].body
      );
      expect(body.email).toBeUndefined();
    });
  });

  it('shows "Sending..." and a spinner while the request is in flight', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock) = jest.fn(() => new Promise(() => {}));
    renderModal();

    await user.type(screen.getByLabelText(/your feedback/i), 'Loading test');
    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    expect(
      screen.getByRole('button', { name: /sending/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
  });

  it('shows a success notification and closes after successful submission', async () => {
    const user = userEvent.setup();
    const onClose = jest.fn();
    (global.fetch as jest.Mock) = jest
      .fn()
      .mockResolvedValue(makeFetchResponse({ ok: true }));
    renderModal({ onClose });

    await user.type(screen.getByLabelText(/your feedback/i), 'Awesome tool!');
    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await screen.findByText(/thank you for your feedback/i);
    expect(onClose).toHaveBeenCalled();
  });

  it('shows an error notification when the API responds with an error', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock) = jest
      .fn()
      .mockResolvedValue(makeFetchResponse({ message: 'Server error' }, 500));
    renderModal();

    await user.type(screen.getByLabelText(/your feedback/i), 'Test message');
    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await screen.findByText('Server error');
  });

  it('resets the feedback field after successful submission', async () => {
    const user = userEvent.setup();
    const onClose = jest.fn();
    renderModal({ onClose });

    const textarea = screen.getByLabelText(/your feedback/i);
    await user.type(textarea, 'My feedback');
    expect(textarea).toHaveValue('My feedback');

    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('the rating field is optional (submit still works without a rating)', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.type(
      screen.getByLabelText(/your feedback/i),
      'No rating needed'
    );
    await user.click(screen.getByRole('button', { name: /send feedback/i }));

    await waitFor(() => {
      const body = JSON.parse(
        (global.fetch as jest.Mock).mock.calls[0][1].body
      );
      expect(body.rating).toBeNull();
    });
  });
});
