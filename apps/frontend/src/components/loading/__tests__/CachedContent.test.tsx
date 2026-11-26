import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import {
  CachedContent,
  SkeletonMode,
  SkeletonSlot,
  useSkeletonMode,
} from '../SkeletonMode';

function Mode() {
  return <span data-testid="mode">{String(useSkeletonMode())}</span>;
}

function View({ active }: { active: boolean }) {
  return (
    <SkeletonMode>
      <CachedContent active={active}>
        <Mode />
        <SkeletonSlot>
          <button>Open</button>
        </SkeletonSlot>
      </CachedContent>
    </SkeletonMode>
  );
}

describe('CachedContent', () => {
  it('draws cached content for real, but inert', () => {
    render(<View active />);

    expect(screen.getByTestId('mode')).toHaveTextContent('false');
    const button = screen.getByText('Open');
    expect(button.closest('.MuiSkeleton-root')).toBeNull();
    expect(button.closest('[inert]')).not.toBeNull();
  });

  it('leaves placeholders as they are without a cache', () => {
    render(<View active={false} />);

    expect(screen.getByTestId('mode')).toHaveTextContent('true');
    expect(
      screen.getByText('Open').closest('.MuiSkeleton-root')
    ).not.toBeNull();
  });
});
