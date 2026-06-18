'use client';

import * as React from 'react';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { Box, Typography } from '@mui/material';
import {
  getOnboardingVideoEmbedUrl,
  getYouTubeThumbnailUrl,
} from '@/utils/onboarding-video';

interface OnboardingVideoPlayerProps {
  videoUrl: string;
}

export default function OnboardingVideoPlayer({
  videoUrl,
}: OnboardingVideoPlayerProps) {
  const [isPlaying, setIsPlaying] = React.useState(false);
  const embedUrl = getOnboardingVideoEmbedUrl(videoUrl);
  const thumbnailUrl = getYouTubeThumbnailUrl(videoUrl);

  if (!embedUrl) {
    return (
      <Box
        sx={{
          width: '100%',
          aspectRatio: '16 / 9',
          borderRadius: '20px',
          bgcolor: '#090909',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: 3,
        }}
      >
        <Typography sx={{ color: 'grey.400', textAlign: 'center' }}>
          Video unavailable. You can continue with setup.
        </Typography>
      </Box>
    );
  }

  if (isPlaying) {
    return (
      <Box
        sx={{
          width: '100%',
          aspectRatio: '16 / 9',
          borderRadius: '20px',
          overflow: 'hidden',
          bgcolor: '#090909',
        }}
      >
        <Box
          component="iframe"
          src={embedUrl}
          title="Onboarding welcome video"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          sx={{
            width: '100%',
            height: '100%',
            border: 0,
          }}
        />
      </Box>
    );
  }

  return (
    <Box
      component="button"
      type="button"
      onClick={() => setIsPlaying(true)}
      aria-label="Play onboarding video"
      sx={{
        width: '100%',
        aspectRatio: '16 / 9',
        borderRadius: '20px',
        overflow: 'hidden',
        bgcolor: '#090909',
        border: 'none',
        cursor: 'pointer',
        position: 'relative',
        p: 0,
        display: 'block',
        backgroundImage: thumbnailUrl ? `url(${thumbnailUrl})` : undefined,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: thumbnailUrl ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.6)',
        }}
      >
        <Box
          sx={{
            width: 72,
            height: 52,
            bgcolor: '#ff0000',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <PlayArrowIcon sx={{ color: 'white', fontSize: 40 }} />
        </Box>
      </Box>
    </Box>
  );
}
