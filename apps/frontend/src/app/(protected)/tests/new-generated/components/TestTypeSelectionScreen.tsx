'use client';

import React from 'react';
import ChatIcon from '@mui/icons-material/Chat';
import ForumIcon from '@mui/icons-material/Forum';
import { TestType } from './shared/types';
import SelectionModal, { SelectionCardConfig } from './shared/SelectionModal';
import ChatPreview from './shared/ChatPreview';

interface TestTypeSelectionScreenProps {
  open: boolean;
  onClose: () => void;
  onSelectTestType: (testType: TestType) => void;
}

/**
 * TestTypeSelectionScreen Component
 * Modal to choose between single-turn and multi-turn tests
 */
export default function TestTypeSelectionScreen({
  open,
  onClose,
  onSelectTestType,
}: TestTypeSelectionScreenProps) {
  const cards: SelectionCardConfig[] = [
    {
      id: 'single-turn',
      title: 'Single-Turn Tests',
      description:
        'Test individual prompts and responses. Best for evaluating specific behaviors, accuracy, and compliance in standalone interactions.',
      icon: <ChatIcon />,
      iconBgColor: 'warning.lighter',
      iconColor: 'warning.main',
      buttonLabel: 'Select Single-Turn',
      buttonVariant: 'outlined',
      onClick: () => onSelectTestType('single_turn'),
      preview: (
        <ChatPreview
          messages={[
            {
              role: 'user',
              content: 'What is the capital of France?',
            },
            {
              role: 'assistant',
              content: 'The capital of France is Paris.',
            },
          ]}
        />
      ),
    },
    {
      id: 'multi-turn',
      title: 'Multi-Turn Tests',
      description:
        'Test conversational scenarios with goals and constraints. Best for evaluating agent behavior across multiple interactions and workflows.',
      icon: <ForumIcon />,
      iconBgColor: 'secondary.lighter',
      iconColor: 'secondary.main',
      buttonLabel: 'Select Multi-Turn',
      buttonVariant: 'contained',
      onClick: () => onSelectTestType('multi_turn'),
      preview: (
        <ChatPreview
          messages={[
            {
              role: 'user',
              content: 'I need to book a flight to Paris',
            },
            {
              role: 'assistant',
              content: 'When would you like to travel?',
            },
            {
              role: 'user',
              content: 'Next week, preferably Monday',
            },
            {
              role: 'assistant',
              content:
                'Great! I found flights on Monday. Would you prefer morning or afternoon?',
            },
            {
              role: 'user',
              content: 'Morning works best for me',
            },
            {
              role: 'assistant',
              content:
                "Perfect! I've found a 9 AM flight. Shall I proceed with the booking?",
            },
          ]}
        />
      ),
    },
  ];

  return (
    <SelectionModal
      open={open}
      onClose={onClose}
      title="Choose Test Type"
      subtitle="Select the type of tests you want to generate for your project"
      cards={cards}
      maxWidth="lg"
      fillHeight
      showIcons={false}
    />
  );
}
