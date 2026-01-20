'use client';

import React, { useState, useEffect } from 'react';
import { Box, Skeleton } from '@mui/material';
import ImageIcon from '@mui/icons-material/Image';
import { API_ENDPOINTS } from '@/utils/api-client/config';

interface TestImageProps {
  testId: string;
  sessionToken: string;
  alt?: string;
  width?: number | string;
  height?: number | string;
  sx?: object;
}

/**
 * Component that fetches and displays an image from a test.
 * Handles loading states and errors gracefully.
 */
export default function TestImage({
  testId,
  sessionToken,
  alt = 'Test image',
  width = 48,
  height = 48,
  sx = {},
}: TestImageProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let isMounted = true;
    let objectUrl: string | null = null;

    const fetchImage = async () => {
      try {
        setLoading(true);
        setError(false);

        const response = await fetch(`${API_ENDPOINTS.tests}/${testId}/image`, {
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
        });

        if (!response.ok) {
          throw new Error('Failed to load image');
        }

        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);

        if (isMounted) {
          setImageUrl(objectUrl);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(true);
          setLoading(false);
        }
      }
    };

    fetchImage();

    return () => {
      isMounted = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [testId, sessionToken]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  const containerStyles = {
    width,
    height,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 1,
    flexShrink: 0,
    border: '1px solid',
    borderColor: 'divider',
    overflow: 'hidden',
    bgcolor: 'action.hover',
    ...sx,
  };

  if (loading) {
    return (
      <Box sx={containerStyles}>
        <Skeleton variant="rectangular" width="100%" height="100%" />
      </Box>
    );
  }

  if (error || !imageUrl) {
    return (
      <Box sx={containerStyles}>
        <ImageIcon sx={{ color: 'text.secondary', fontSize: 28 }} />
      </Box>
    );
  }

  return (
    <Box
      component="img"
      src={imageUrl}
      alt={alt}
      sx={{
        width,
        height,
        objectFit: 'cover',
        borderRadius: 1,
        flexShrink: 0,
        border: '1px solid',
        borderColor: 'divider',
        ...sx,
      }}
    />
  );
}

