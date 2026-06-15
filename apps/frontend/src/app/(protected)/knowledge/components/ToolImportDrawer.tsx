'use client';

import React, { useState, useEffect, useCallback } from 'react';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import BaseDrawer from '@/components/common/BaseDrawer';
import { Tool } from '@/utils/api-client/interfaces/tool';
import ToolSelectorPanel from './ToolSelectorPanel';
import ToolImportPanel from './ToolImportPanel';

interface ToolImportDrawerProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  sessionToken: string;
}

type Step = 'select' | 'import';

export default function ToolImportDrawer({
  open,
  onClose,
  onSuccess,
  sessionToken,
}: ToolImportDrawerProps) {
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
        title="Select Tool"
        titleIcon={<CloudDownloadIcon color="primary" />}
        closeButtonText="Cancel"
        width={900}
      >
        <ToolSelectorPanel
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
      title="Import from Tool"
      titleIcon={<CloudDownloadIcon color="primary" />}
      width={900}
      closeButtonText="Cancel"
      showHeader={true}
    >
      <ToolImportPanel
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
