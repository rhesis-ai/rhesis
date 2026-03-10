'use client'

import React from 'react'

const styles = {
  container: {
    position: 'relative',
    paddingBottom: '56.25%',
    height: 0,
    overflow: 'hidden',
    marginBottom: '2rem',
  },
  iframe: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
  },
}

export const YouTubeEmbed = ({ videoId }) => {
  return (
    <div style={styles.container}>
      <iframe
        src={`https://www.youtube.com/embed/${videoId}`}
        style={styles.iframe}
        frameBorder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  )
}
