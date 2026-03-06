import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SidebarFooter from '../SidebarFooter';

jest.mock('@/components/common/FeedbackModal', () => ({
  __esModule: true,
  default: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? (
      <div data-testid="feedback-modal">
        <button onClick={onClose}>close-feedback</button>
      </div>
    ) : null,
}));

describe('SidebarFooter', () => {
  it('renders a Feedback button in expanded mode (mini=false)', () => {
    render(<SidebarFooter mini={false} />);
    expect(
      screen.getByRole('button', { name: /feedback/i })
    ).toBeInTheDocument();
  });

  it('renders a Feedback button in mini mode', () => {
    render(<SidebarFooter mini={true} />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('opens the feedback modal when the button is clicked', async () => {
    const user = userEvent.setup();
    render(<SidebarFooter />);

    await user.click(screen.getByRole('button', { name: /feedback/i }));
    expect(screen.getByTestId('feedback-modal')).toBeInTheDocument();
  });

  it('closes the feedback modal when onClose is called', async () => {
    const user = userEvent.setup();
    render(<SidebarFooter />);

    await user.click(screen.getByRole('button', { name: /feedback/i }));
    expect(screen.getByTestId('feedback-modal')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /close-feedback/i }));
    expect(screen.queryByTestId('feedback-modal')).not.toBeInTheDocument();
  });

  it('shows the app version text in expanded mode', () => {
    process.env.APP_VERSION = '1.2.3';
    render(<SidebarFooter mini={false} />);
    expect(screen.getByText('v1.2.3')).toBeInTheDocument();
    delete process.env.APP_VERSION;
  });

  it('falls back to v0.0.0 when APP_VERSION is not set', () => {
    delete process.env.APP_VERSION;
    render(<SidebarFooter mini={false} />);
    expect(screen.getByText('v0.0.0')).toBeInTheDocument();
  });
});
