import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { UserAvatar } from '../UserAvatar';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

describe('UserAvatar', () => {
  it('renders with user name initial', () => {
    render(<UserAvatar userName="Alice" />);
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('renders uppercase initial', () => {
    render(<UserAvatar userName="bob" />);
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('renders fallback "U" when no name provided', () => {
    render(<UserAvatar />);
    expect(screen.getByText('U')).toBeInTheDocument();
  });

  it('renders with user picture', () => {
    render(
      <UserAvatar userName="Alice" userPicture="https://example.com/pic.jpg" />
    );
    const avatar = screen.getByRole('img');
    expect(avatar).toHaveAttribute('src', 'https://example.com/pic.jpg');
    expect(avatar).toHaveAttribute('alt', 'Alice');
  });

  it('uses "User" as alt text when no name provided', () => {
    render(<UserAvatar userPicture="https://example.com/pic.jpg" />);
    const avatar = screen.getByRole('img');
    expect(avatar).toHaveAttribute('alt', 'User');
  });

  it('defaults to LARGE size', () => {
    const { container } = render(<UserAvatar userName="A" />);
    const avatar = container.querySelector('.MuiAvatar-root');
    expect(avatar).toHaveStyle({
      width: `${AVATAR_SIZES.LARGE}px`,
      height: `${AVATAR_SIZES.LARGE}px`,
    });
  });

  it('supports custom size', () => {
    const { container } = render(
      <UserAvatar userName="A" size={AVATAR_SIZES.SMALL} />
    );
    const avatar = container.querySelector('.MuiAvatar-root');
    expect(avatar).toHaveStyle({
      width: `${AVATAR_SIZES.SMALL}px`,
      height: `${AVATAR_SIZES.SMALL}px`,
    });
  });
});
