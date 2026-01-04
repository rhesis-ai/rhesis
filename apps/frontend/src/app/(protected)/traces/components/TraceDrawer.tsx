'use client';

interface TraceDrawerProps {
  open: boolean;
  onClose: () => void;
  traceId: string | null;
  projectId: string;
  sessionToken: string;
}

export default function TraceDrawer({
  open,
  onClose,
  traceId,
  projectId,
  sessionToken,
}: TraceDrawerProps) {
  return null; // Will be implemented in WP4
}
