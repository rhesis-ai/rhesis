'use client';

import { WebSocketProvider } from '@/contexts/WebSocketContext';

export default function ArchitectLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}
