'use client';

import dynamic from 'next/dynamic';

// Create a client-only version of the component
const ProjectSankey = dynamic(() => import('./ProjectSankeyClient'), {
  ssr: false,
  loading: () => (
    <div 
      style={{ 
        height: 500, 
        width: '100%',
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        border: '1px solid rgba(0, 0, 0, 0.23)',
        borderRadius: '4px',
        backgroundColor: '#f5f5f5'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div>Loading flow diagram...</div>
      </div>
    </div>
  )
});

export default ProjectSankey; 