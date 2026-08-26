import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';
import DensityControl from '../DensityControl';

describe('DensityControl', () => {
  it('exposes a radiogroup with three radio options', () => {
    render(<DensityControl density="shape" onChange={jest.fn()} />);

    expect(screen.getByRole('radiogroup')).toBeInTheDocument();
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(3);
  });

  it('marks only the current density as checked', () => {
    render(<DensityControl density="detail" onChange={jest.fn()} />);

    expect(screen.getByRole('radio', { name: 'Numbers' })).toHaveAttribute(
      'aria-checked',
      'false'
    );
    expect(
      screen.getByRole('radio', { name: 'Numbers + Shape' })
    ).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('radio', { name: 'Detail' })).toHaveAttribute(
      'aria-checked',
      'true'
    );
  });

  it('uses roving tabindex: only the checked option is a tab stop', () => {
    render(<DensityControl density="numbers" onChange={jest.fn()} />);

    expect(screen.getByRole('radio', { name: 'Numbers' })).toHaveAttribute(
      'tabIndex',
      '0'
    );
    expect(
      screen.getByRole('radio', { name: 'Numbers + Shape' })
    ).toHaveAttribute('tabIndex', '-1');
    expect(screen.getByRole('radio', { name: 'Detail' })).toHaveAttribute(
      'tabIndex',
      '-1'
    );
  });

  it('calls onChange when a radio is clicked', () => {
    const onChange = jest.fn();
    render(<DensityControl density="numbers" onChange={onChange} />);

    fireEvent.click(screen.getByRole('radio', { name: 'Detail' }));
    expect(onChange).toHaveBeenCalledWith('detail');
  });

  it('moves selection right with ArrowRight', () => {
    const onChange = jest.fn();
    render(<DensityControl density="numbers" onChange={onChange} />);

    fireEvent.keyDown(screen.getByRole('radio', { name: 'Numbers' }), {
      key: 'ArrowRight',
    });
    expect(onChange).toHaveBeenCalledWith('shape');
  });

  it('moves selection left with ArrowLeft, wrapping at the start', () => {
    const onChange = jest.fn();
    render(<DensityControl density="numbers" onChange={onChange} />);

    fireEvent.keyDown(screen.getByRole('radio', { name: 'Numbers' }), {
      key: 'ArrowLeft',
    });
    expect(onChange).toHaveBeenCalledWith('detail');
  });

  it('wraps to the first option with ArrowRight from the last', () => {
    const onChange = jest.fn();
    render(<DensityControl density="detail" onChange={onChange} />);

    fireEvent.keyDown(screen.getByRole('radio', { name: 'Detail' }), {
      key: 'ArrowRight',
    });
    expect(onChange).toHaveBeenCalledWith('numbers');
  });

  it('jumps to the first/last option with Home/End', () => {
    const onChange = jest.fn();
    render(<DensityControl density="shape" onChange={onChange} />);

    fireEvent.keyDown(screen.getByRole('radio', { name: 'Numbers + Shape' }), {
      key: 'Home',
    });
    expect(onChange).toHaveBeenLastCalledWith('numbers');

    fireEvent.keyDown(screen.getByRole('radio', { name: 'Numbers + Shape' }), {
      key: 'End',
    });
    expect(onChange).toHaveBeenLastCalledWith('detail');
  });
});
