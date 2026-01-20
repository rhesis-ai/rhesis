'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Skeleton,
  Modal,
  IconButton,
  Typography,
  Fade,
  Backdrop,
  alpha,
} from '@mui/material';
import ImageIcon from '@mui/icons-material/Image';
import CloseIcon from '@mui/icons-material/Close';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { TestsClient } from '@/utils/api-client/tests-client';

interface TestImageProps {
  testId: string;
  sessionToken: string;
  alt?: string;
  width?: number | string;
  height?: number | string;
  sx?: object;
  /** Enable clicking the thumbnail to open a full-size lightbox view */
  enableLightbox?: boolean;
  /** Array of all test IDs for lightbox navigation (enables prev/next buttons) */
  allTestIds?: string[];
  /** Callback when user navigates to a different image in the lightbox */
  onNavigate?: (testId: string) => void;
}

/**
 * Component that fetches and displays an image from a test.
 * Handles loading states and errors gracefully.
 * Optionally supports a lightbox modal for viewing the full-size image.
 */
export default function TestImage({
  testId,
  sessionToken,
  alt = 'Test image',
  width = 48,
  height = 48,
  sx = {},
  enableLightbox = true,
  allTestIds,
  onNavigate,
}: TestImageProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  // Lightbox navigation state
  const [lightboxTestId, setLightboxTestId] = useState(testId);
  const [lightboxImageUrl, setLightboxImageUrl] = useState<string | null>(null);
  const [lightboxLoading, setLightboxLoading] = useState(false);

  // Calculate navigation state
  const currentIndex = allTestIds?.indexOf(lightboxTestId) ?? -1;
  const hasPrevious = currentIndex > 0;
  const hasNext = allTestIds ? currentIndex < allTestIds.length - 1 : false;
  const canNavigate = allTestIds && allTestIds.length > 1;

  // Fetch the thumbnail image
  useEffect(() => {
    let isMounted = true;
    let objectUrl: string | null = null;

    const fetchImage = async () => {
      try {
        setLoading(true);
        setError(false);

        const testsClient = new TestsClient(sessionToken);
        const blob = await testsClient.getTestImage(testId);
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

  // Fetch lightbox image when navigating
  useEffect(() => {
    if (!lightboxOpen) return;

    let isMounted = true;
    let objectUrl: string | null = null;

    const fetchLightboxImage = async () => {
      // If it's the same as the thumbnail, reuse that URL
      if (lightboxTestId === testId && imageUrl) {
        setLightboxImageUrl(imageUrl);
        return;
      }

      try {
        setLightboxLoading(true);

        const testsClient = new TestsClient(sessionToken);
        const blob = await testsClient.getTestImage(lightboxTestId);
        objectUrl = URL.createObjectURL(blob);

        if (isMounted) {
          setLightboxImageUrl(objectUrl);
          setLightboxLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setLightboxImageUrl(null);
          setLightboxLoading(false);
        }
      }
    };

    fetchLightboxImage();

    return () => {
      isMounted = false;
      // Only revoke if it's not the same as the thumbnail URL
      if (objectUrl && objectUrl !== imageUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [lightboxOpen, lightboxTestId, testId, imageUrl, sessionToken]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  const handleOpenLightbox = useCallback(
    (e: React.MouseEvent) => {
      if (enableLightbox && imageUrl) {
        e.stopPropagation(); // Prevent row click in grid
        setLightboxTestId(testId); // Reset to current test
        setLightboxOpen(true);
      }
    },
    [enableLightbox, imageUrl, testId]
  );

  const handleCloseLightbox = useCallback(() => {
    setLightboxOpen(false);
    // Clean up lightbox image URL if different from thumbnail
    if (lightboxImageUrl && lightboxImageUrl !== imageUrl) {
      URL.revokeObjectURL(lightboxImageUrl);
      setLightboxImageUrl(null);
    }
  }, [lightboxImageUrl, imageUrl]);

  const handlePrevious = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (hasPrevious && allTestIds) {
        const prevId = allTestIds[currentIndex - 1];
        setLightboxTestId(prevId);
        onNavigate?.(prevId);
      }
    },
    [hasPrevious, allTestIds, currentIndex, onNavigate]
  );

  const handleNext = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (hasNext && allTestIds) {
        const nextId = allTestIds[currentIndex + 1];
        setLightboxTestId(nextId);
        onNavigate?.(nextId);
      }
    },
    [hasNext, allTestIds, currentIndex, onNavigate]
  );

  // Keyboard navigation
  useEffect(() => {
    if (!lightboxOpen || !canNavigate) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' && hasPrevious && allTestIds) {
        const prevId = allTestIds[currentIndex - 1];
        setLightboxTestId(prevId);
        onNavigate?.(prevId);
      } else if (e.key === 'ArrowRight' && hasNext && allTestIds) {
        const nextId = allTestIds[currentIndex + 1];
        setLightboxTestId(nextId);
        onNavigate?.(nextId);
      } else if (e.key === 'Escape') {
        handleCloseLightbox();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    lightboxOpen,
    canNavigate,
    hasPrevious,
    hasNext,
    allTestIds,
    currentIndex,
    onNavigate,
    handleCloseLightbox,
  ]);

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
    position: 'relative',
    ...(enableLightbox && imageUrl
      ? {
          cursor: 'pointer',
          '&:hover': {
            '& .zoom-overlay': {
              opacity: 1,
            },
          },
        }
      : {}),
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
    <>
      <Box sx={containerStyles} onClick={handleOpenLightbox}>
        <Box
          component="img"
          src={imageUrl}
          alt={alt}
          sx={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
        {enableLightbox && (
          <Box
            className="zoom-overlay"
            sx={theme => ({
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              bgcolor: alpha(theme.palette.common.black, 0.4),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: 0,
              transition: theme.transitions.create('opacity', {
                duration: theme.transitions.duration.short,
              }),
            })}
          >
            <ZoomOutMapIcon sx={{ color: 'common.white', fontSize: 20 }} />
          </Box>
        )}
      </Box>

      {/* Lightbox Modal */}
      <Modal
        open={lightboxOpen}
        onClose={handleCloseLightbox}
        closeAfterTransition
        slots={{ backdrop: Backdrop }}
        slotProps={{
          backdrop: {
            timeout: 300,
            sx: theme => ({
              bgcolor: alpha(theme.palette.common.black, 0.9),
            }),
          },
        }}
      >
        <Fade in={lightboxOpen}>
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              outline: 'none',
            }}
          >
            {/* Close button */}
            <IconButton
              onClick={handleCloseLightbox}
              sx={theme => ({
                position: 'absolute',
                top: 16,
                right: 16,
                color: 'common.white',
                bgcolor: alpha(theme.palette.common.white, 0.1),
                '&:hover': {
                  bgcolor: alpha(theme.palette.common.white, 0.2),
                },
                zIndex: 1,
              })}
            >
              <CloseIcon />
            </IconButton>

            {/* Previous button */}
            {canNavigate && (
              <IconButton
                onClick={handlePrevious}
                disabled={!hasPrevious}
                sx={theme => ({
                  position: 'absolute',
                  left: 16,
                  color: 'common.white',
                  bgcolor: alpha(theme.palette.common.white, 0.1),
                  '&:hover': {
                    bgcolor: alpha(theme.palette.common.white, 0.2),
                  },
                  '&.Mui-disabled': {
                    color: alpha(theme.palette.common.white, 0.3),
                    bgcolor: alpha(theme.palette.common.white, 0.05),
                  },
                  zIndex: 1,
                })}
              >
                <ChevronLeftIcon sx={{ fontSize: 32 }} />
              </IconButton>
            )}

            {/* Next button */}
            {canNavigate && (
              <IconButton
                onClick={handleNext}
                disabled={!hasNext}
                sx={theme => ({
                  position: 'absolute',
                  right: 16,
                  color: 'common.white',
                  bgcolor: alpha(theme.palette.common.white, 0.1),
                  '&:hover': {
                    bgcolor: alpha(theme.palette.common.white, 0.2),
                  },
                  '&.Mui-disabled': {
                    color: alpha(theme.palette.common.white, 0.3),
                    bgcolor: alpha(theme.palette.common.white, 0.05),
                  },
                  zIndex: 1,
                })}
              >
                <ChevronRightIcon sx={{ fontSize: 32 }} />
              </IconButton>
            )}

            {/* Image container */}
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                maxWidth: '80vw',
                maxHeight: '90vh',
              }}
            >
              {/* Loading state */}
              {lightboxLoading ? (
                <Box
                  sx={theme => ({
                    width: 400,
                    height: 400,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: alpha(theme.palette.common.white, 0.1),
                    borderRadius: 2,
                  })}
                >
                  <Skeleton
                    variant="rectangular"
                    width="100%"
                    height="100%"
                    sx={theme => ({
                      bgcolor: alpha(theme.palette.common.white, 0.1),
                    })}
                  />
                </Box>
              ) : lightboxImageUrl ? (
                <Box
                  component="img"
                  src={lightboxImageUrl}
                  alt={alt}
                  sx={theme => ({
                    maxWidth: '80vw',
                    maxHeight: '80vh',
                    objectFit: 'contain',
                    borderRadius: 2,
                    boxShadow: theme.shadows[24],
                  })}
                />
              ) : (
                <Box
                  sx={theme => ({
                    width: 200,
                    height: 200,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: alpha(theme.palette.common.white, 0.1),
                    borderRadius: 2,
                  })}
                >
                  <ImageIcon
                    sx={theme => ({
                      fontSize: 64,
                      color: alpha(theme.palette.common.white, 0.5),
                    })}
                  />
                </Box>
              )}

              {/* Caption and counter */}
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                {canNavigate && (
                  <Typography
                    variant="caption"
                    sx={theme => ({
                      color: alpha(theme.palette.common.white, 0.6),
                      display: 'block',
                      mb: 0.5,
                    })}
                  >
                    {currentIndex + 1} / {allTestIds?.length}
                  </Typography>
                )}
                {alt && alt !== 'Test image' && (
                  <Typography
                    variant="body2"
                    sx={theme => ({
                      color: alpha(theme.palette.common.white, 0.8),
                      maxWidth: '60vw',
                    })}
                  >
                    {alt}
                  </Typography>
                )}
              </Box>
            </Box>
          </Box>
        </Fade>
      </Modal>
    </>
  );
}
