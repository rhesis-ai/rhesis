'use client';

import React from 'react';
import { Box } from '@mui/material';
import { keyframes } from '@mui/system';

const bounce = keyframes`
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
`;

interface ThinkingDotsProps {
  size?: number;
  color?: string;
}

export default function ThinkingDots({
  size = 5,
  color = 'text.secondary',
}: ThinkingDotsProps) {
  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: `${size * 0.6}px`,
        height: size * 2,
      }}
    >
      {[0, 1, 2].map(i => (
        <Box
          key={i}
          sx={{
            width: size,
            height: size,
            borderRadius: (theme) => theme.shape.circular,
            bgcolor: color,
            animation: `${bounce} 1.2s ease-in-out infinite`,
            animationDelay: `${i * 0.15}s`,
          }}
        />
      ))}
    </Box>
  );
}
