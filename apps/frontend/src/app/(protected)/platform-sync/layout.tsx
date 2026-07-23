import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Platform Sync',
};

export default function PlatformSyncLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
