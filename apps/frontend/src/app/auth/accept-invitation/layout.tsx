import { Metadata } from 'next';

export const metadata: Metadata = { title: 'Accept invitation' };

export default function AcceptInvitationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
