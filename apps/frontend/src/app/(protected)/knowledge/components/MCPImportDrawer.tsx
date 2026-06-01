'use client';

import React, { useState, useEffect, useCallback } from 'react';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import TerminalIcon from '@mui/icons-material/Terminal';
import BaseDrawer from '@/components/common/BaseDrawer';
import { Tool } from '@/utils/api-client/interfaces/tool';
import MCPToolSelectorPanel from './MCPToolSelectorPanel';
import MCPImportPanel from './MCPImportPanel';

interface MCPImportDrawerProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  sessionToken: string;
}

type Step = 'select' | 'import';

export default function MCPImportDrawer({
  open,
  onClose,
  onSuccess,
  sessionToken,
}: MCPImportDrawerProps) {
  const [step, setStep] = useState<Step>('select');
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null);

  const resetState = useCallback(() => {
    setStep('select');
    setSelectedTool(null);
  }, []);

  useEffect(() => {
    if (!open) {
      resetState();
    }
  }, [open, resetState]);

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleSelectTool = (tool: Tool) => {
    setSelectedTool(tool);
    setStep('import');
  };

  const handleBack = () => {
    setStep('select');
    setSelectedTool(null);
  };

  const handleImportSuccess = () => {
    handleClose();
    onSuccess?.();
  };

  if (step === 'select') {
    return (
      <BaseDrawer
        open={open}
        onClose={handleClose}
        title="Select MCP Tool"
        titleIcon={<TerminalIcon color="primary" />}
        closeButtonText="Cancel"
      >
        <MCPToolSelectorPanel
          open={open}
          onClose={handleClose}
          onSelectTool={handleSelectTool}
          sessionToken={sessionToken}
        />
      </BaseDrawer>
    );
  }

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Import from MCP"
      titleIcon={<CloudDownloadIcon color="primary" />}
      width={900}
      closeButtonText="Cancel"
      showHeader={true}
    >
      <MCPImportPanel
        open={open}
        onClose={handleClose}
        onBack={handleBack}
        onSuccess={handleImportSuccess}
        sessionToken={sessionToken}
        tool={selectedTool}
      />
    </BaseDrawer>
  );
}
