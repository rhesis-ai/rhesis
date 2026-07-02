import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';

jest.mock('../MappingEditor', () => {
  return {
    __esModule: true,
    default: () => <div data-testid="test-and-map" />,
  };
});

import TabMapping from '../TabMapping';

const defaultProps = {
  reqBody: '{"input": "{{ input }}"}',
  resBody: '{"output": "$.choices[0].message.content"}',
  onReqBodyChange: jest.fn(),
  onResBodyChange: jest.fn(),
  testResult: null,
  isTestingEndpoint: false,
  onRunTest: jest.fn(),
  onAutoConfigureOpen: jest.fn(),
};

describe('TabMapping', () => {
  it('renders the Auto Mapping button', () => {
    render(<TabMapping {...defaultProps} />);
    expect(
      screen.getByRole('button', { name: /auto mapping/i })
    ).toBeInTheDocument();
  });

  it('calls onAutoConfigureOpen when Auto Mapping button is clicked', async () => {
    const onAutoConfigureOpen = jest.fn();
    const user = userEvent.setup({ delay: null });
    render(
      <TabMapping {...defaultProps} onAutoConfigureOpen={onAutoConfigureOpen} />
    );
    await user.click(screen.getByRole('button', { name: /auto mapping/i }));
    expect(onAutoConfigureOpen).toHaveBeenCalledTimes(1);
  });

  it('renders the Manual Mapping section', () => {
    render(<TabMapping {...defaultProps} />);
    expect(screen.getByText(/manual mapping/i)).toBeInTheDocument();
  });

  it('expands Manual Mapping section when expand control is clicked', async () => {
    render(<TabMapping {...defaultProps} />);
    fireEvent.click(
      screen.getByRole('button', { name: /expand manual mapping/i })
    );
    expect(screen.getByTestId('test-and-map')).toBeInTheDocument();
  });

  it('renders the Auto Mapping description text', () => {
    render(<TabMapping {...defaultProps} />);
    expect(
      screen.getByText(/paste your api docs or a sample response/i)
    ).toBeInTheDocument();
  });
});
