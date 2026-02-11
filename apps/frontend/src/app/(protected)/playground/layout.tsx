'use client';

import { WebSocketProvider } from '@/contexts/WebSocketContext';

export default function PlaygroundLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}
