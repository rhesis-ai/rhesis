'use client';

import { useCallback, useEffect, useState } from 'react';
import { Box } from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import TraceExplorer from './TraceExplorer';

interface TraceDrawerProps {
  open: boolean;
  onClose: () => void;
  traceId: string | null;
  projectId: string;
  initialTurnIndex?: number;
  /** OTel span_id to select on open; takes precedence over initialTurnIndex. */
  initialSpanId?: string;
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  onTraceUpdated?: () => void;
}

/** TraceExplorer in a resizable right-hand drawer that closes on Esc. */
export default function TraceDrawer({
  open,
  onClose,
  ...explorerProps
}: TraceDrawerProps) {
  const [drawerWidth, setDrawerWidth] = useState(85); // viewport percentage
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;
    const handleMove = (e: MouseEvent) => {
      const newWidth =
        ((window.innerWidth - e.clientX) / window.innerWidth) * 100;
      setDrawerWidth(Math.min(Math.max(newWidth, 30), 95));
    };
    const handleUp = () => setIsResizing(false);
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ew-resize';
    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isResizing]);

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      width={`${drawerWidth}%`}
      showHeader={false}
      closeButtonText=""
      contentLayout="fill"
      disablePadding
    >
      <Box
        sx={{
          position: 'relative',
          height: '100%',
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Drawer width resize handle */}
        <Box
          onMouseDown={handleResizeStart}
          sx={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: theme => theme.spacing(0.75),
            cursor: 'ew-resize',
            zIndex: 10,
            '&::after': {
              content: '""',
              position: 'absolute',
              left: 0,
              top: 0,
              bottom: 0,
              width: theme => theme.spacing(0.375),
              backgroundColor: theme =>
                isResizing ? theme.palette.primary.main : 'transparent',
              transition: theme =>
                isResizing
                  ? 'none'
                  : theme.transitions.create('background-color'),
            },
            '&:hover::after': {
              backgroundColor: theme => theme.palette.primary.main,
            },
          }}
        />
        <TraceExplorer active={open} onClose={onClose} {...explorerProps} />
      </Box>
    </BaseDrawer>
  );
}
