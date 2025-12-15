import React from 'react'

const FileTree = ({ data, title = 'Project Structure' }) => {
  const styles = {
    container: {
      background: '#0d1117',
      border: '1px solid #2c2c2c',
      borderRadius: '8px',
      overflow: 'hidden',
      fontFamily:
        "'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace",
      fontSize: '14px',
      margin: '16px 0',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
      fontFeatureSettings: '"liga" 0, "calt" 0',
    },
    header: {
      background: '#161b22',
      padding: '12px 16px',
      borderBottom: '1px solid #2c2c2c',
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
    },
    controls: {
      display: 'flex',
      gap: '6px',
    },
    dot: {
      width: '12px',
      height: '12px',
      borderRadius: '50%',
    },
    dotRed: {
      background: '#ff5f57',
    },
    dotYellow: {
      background: '#ffbd2e',
    },
    dotGreen: {
      background: '#28ca42',
    },
    title: {
      color: '#f0f6fc',
      fontWeight: '600',
      fontSize: '13px',
    },
    content: {
      padding: '8px 0',
      maxHeight: '600px',
      overflowY: 'auto',
    },
    item: {
      display: 'flex',
      alignItems: 'center',
      padding: '2px 12px',
      color: '#e6edf3',
      lineHeight: '1.4',
      fontFamily:
        "'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace",
      fontSize: '14px',
      fontFeatureSettings: '"liga" 0, "calt" 0',
    },
    itemFolder: {
      color: '#79c0ff',
    },
    itemFile: {
      color: '#e6edf3',
    },
    treeStructure: {
      color: '#8b949e',
      margin: '0 8px 0 0',
      padding: '0',
      fontFamily:
        "'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace",
      fontSize: '14px',
      lineHeight: '1.4',
      letterSpacing: '0',
      display: 'inline-block',
      verticalAlign: 'top',
    },
    name: {
      fontWeight: '500',
      flexShrink: 0,
    },
    description: {
      color: '#8b949e',
      fontWeight: '400',
      marginLeft: 'auto',
      fontSize: '12px',
      fontStyle: 'italic',
      opacity: 0.7,
      paddingLeft: '8px',
    },
  }
  const renderNode = (node, depth = 0, isLast = false, prefix = '') => {
    const connector = isLast ? '└── ' : '├── '
    const childPrefix = isLast ? '    ' : '│   '

    return (
      <div key={`${prefix}${node.name}`}>
        <div
          style={{
            ...styles.item,
            ...(node.type === 'folder' ? styles.itemFolder : styles.itemFile),
          }}
        >
          <pre style={styles.treeStructure}>
            {prefix}
            {connector}
          </pre>
          <span style={styles.name}>{node.name}</span>
          {node.description && <span style={styles.description}># {node.description}</span>}
        </div>

        {node.type === 'folder' && node.children && node.children.length > 0 && (
          <div>
            {node.children.map((child, index) => {
              const isLast = index === node.children.length - 1
              return (
                <div key={`${prefix}-${depth}-${child.name}`}>
                  {renderNode(child, depth + 1, isLast, prefix + childPrefix)}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.controls}>
          <div style={{ ...styles.dot, ...styles.dotRed }}></div>
          <div style={{ ...styles.dot, ...styles.dotYellow }}></div>
          <div style={{ ...styles.dot, ...styles.dotGreen }}></div>
        </div>
        <div style={styles.title}>{title}</div>
      </div>
      <div style={styles.content}>
        {data && data.map((node, index) => {
          const isLast = index === data.length - 1
          return (
            <div key={`root-${node.name}`}>
              {renderNode(node, 0, isLast, '')}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export { FileTree }
