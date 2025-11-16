import { type ReactNode } from 'react';
import { type Theme } from '@mui/material/styles';
import { type Session } from 'next-auth';

export interface NavigationPageItem {
  kind: 'page';
  segment: string;
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children?: NavigationPageItem[];
  requireSuperuser?: boolean;
}

export interface NavigationHeaderItem {
  kind: 'header';
  title: string;
}

export interface NavigationDividerItem {
  kind: 'divider';
}

export type NavigationItem =
  | NavigationPageItem
  | NavigationHeaderItem
  | NavigationDividerItem;

export interface BrandingProps {
  title: string;
  logo: ReactNode;
}

export interface AuthenticationProps {
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

export interface NavigationContextProps {
  navigation: NavigationItem[];
  branding: BrandingProps;
  session: Session | null;
  authentication: AuthenticationProps;
  theme: Theme;
}

// Props shared between layout components
export interface LayoutProps {
  children: ReactNode;
  session: Session | null;
  navigation: NavigationItem[];
  branding: BrandingProps;
  authentication: AuthenticationProps;
  theme: Theme;
}
