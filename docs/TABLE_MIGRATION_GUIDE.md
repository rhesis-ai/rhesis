# Table Component Migration Guide

## Overview

A new custom `Table` component has been created to replace Markdown tables in the documentation. This component provides:

- ✅ Full-width layout that uses all available horizontal space
- ✅ Theme-aware styling matching Rhesis brand colors
- ✅ Automatic code formatting for commands and technical content
- ✅ Responsive design for mobile devices
- ✅ Hover effects and striped rows for better readability
- ✅ Dark mode support

## How to Use

### 1. Import the Component

At the top of your MDX file, add:

```mdx
import { Table } from '@/components/Table'
```

### 2. Convert Your Markdown Tables

**Old Markdown Table:**
```markdown
| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| **PostgreSQL** | 5432 | Primary database | `pg_isready` |
| **Redis** | 6379 | Cache & message broker | `redis-cli ping` |
| **Backend** | 8080 | FastAPI application | `curl /health` |
```

**New Table Component:**
```mdx
<Table
  headers={['Service', 'Port', 'Description', 'Health Check']}
  rows={[
    ['PostgreSQL', '5432', 'Primary database', '`pg_isready`'],
    ['Redis', '6379', 'Cache & message broker', '`redis-cli ping`'],
    ['Backend', '8080', 'FastAPI application', '`curl /health`'],
  ]}
/>
```

## Examples from self-hosting.mdx

### Services Table (Lines 143-149)

**Before:**
```markdown
| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| **PostgreSQL** | 5432 | Primary database | `pg_isready` |
| **Redis** | 6379 | Cache & message broker | `redis-cli ping` |
| **Backend** | 8080 | FastAPI application | `curl /health` |
| **Worker** | 8081 | Celery background tasks | `curl /health/basic` |
| **Frontend** | 3000 | Next.js application | `curl /api/auth/session` |
```

**After:**
```mdx
<Table
  headers={['Service', 'Port', 'Description', 'Health Check']}
  rows={[
    ['PostgreSQL', '5432', 'Primary database', '`pg_isready`'],
    ['Redis', '6379', 'Cache & message broker', '`redis-cli ping`'],
    ['Backend', '8080', 'FastAPI application', '`curl /health`'],
    ['Worker', '8081', 'Celery background tasks', '`curl /health/basic`'],
    ['Frontend', '3000', 'Next.js application', '`curl /api/auth/session`'],
  ]}
  align={['left', 'center', 'left', 'left']}
/>
```

### System Requirements Table (Lines 21-26)

**Before:**
```markdown
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **RAM** | 4 GB | 6 GB |
| **Storage** | 8 GB free | 15 GB free |
| **CPU** | 2 cores | 4 cores |
| **Network** | Stable internet | Broadband |
```

**After:**
```mdx
<Table
  headers={['Resource', 'Minimum', 'Recommended']}
  rows={[
    ['RAM', '4 GB', '6 GB'],
    ['Storage', '8 GB free', '15 GB free'],
    ['CPU', '2 cores', '4 cores'],
    ['Network', 'Stable internet', 'Broadband'],
  ]}
  align={['left', 'center', 'center']}
/>
```

### Memory Usage Table (Lines 54-62)

**Before:**
```markdown
| Service | Development | Production |
|---------|-------------|------------|
| **PostgreSQL** | ~256 MB | ~1-2 GB |
| **Redis** | ~50 MB | ~500 MB - 1 GB |
| **Backend** | ~150 MB | ~500 MB - 1 GB |
| **Worker** | ~200 MB | ~1-2 GB |
| **Frontend** | ~100 MB | ~200-400 MB |
| **Docker Overhead** | ~300 MB | ~500 MB - 1 GB |
| **Total Estimated** | **~1.1 GB** | **~3.7-7.1 GB** |
```

**After:**
```mdx
<Table
  caption="Memory Usage by Environment"
  headers={['Service', 'Development', 'Production']}
  rows={[
    ['PostgreSQL', '~256 MB', '~1-2 GB'],
    ['Redis', '~50 MB', '~500 MB - 1 GB'],
    ['Backend', '~150 MB', '~500 MB - 1 GB'],
    ['Worker', '~200 MB', '~1-2 GB'],
    ['Frontend', '~100 MB', '~200-400 MB'],
    ['Docker Overhead', '~300 MB', '~500 MB - 1 GB'],
    ['Total Estimated', '~1.1 GB', '~3.7-7.1 GB'],
  ]}
  align={['left', 'right', 'right']}
/>
```

## Advanced Features

### Custom Alignment

Control text alignment per column:

```mdx
<Table
  headers={['Name', 'Value', 'Description']}
  rows={[
    ['API Key', 'abc123', 'Your authentication key'],
    ['Port', '8080', 'Default server port'],
  ]}
  align={['left', 'center', 'left']}
/>
```

### With Caption

Add a caption to your table:

```mdx
<Table
  caption="Production Environment Requirements"
  headers={['Resource', 'Minimum', 'Recommended']}
  rows={[
    ['RAM', '8 GB', '16 GB'],
    ['CPU', '4 cores', '8 cores'],
  ]}
/>
```

### Disable Striped Rows

For simpler tables:

```mdx
<Table
  headers={['Key', 'Value']}
  rows={[
    ['SMTP_HOST', 'smtp.example.com'],
    ['SMTP_PORT', '465'],
  ]}
  striped={false}
/>
```

## Benefits

1. **Full Width**: Tables now use 100% of available width, making better use of screen space
2. **Consistent Styling**: All tables follow the Rhesis brand guidelines
3. **Better Readability**: Automatic striping, hover effects, and proper spacing
4. **Code Formatting**: Technical content (ports, commands) is automatically formatted
5. **Responsive**: Tables adapt to mobile screens with appropriate sizing
6. **Dark Mode**: Perfect support for light and dark themes
7. **Typography**: Uses Sora for headers and Be Vietnam Pro for content

## Notes

- The component automatically detects code-like content (commands, ports, paths) and formats them
- Wrap content in backticks to force code formatting: `` `curl /health` ``
- Use `align` prop to control column alignment: `['left', 'center', 'right']`
- Striped rows are enabled by default but can be disabled with `striped={false}`
- Hover effects are enabled by default but can be disabled with `hoverable={false}`

## Migration Checklist

For each MDX file with tables:

- [ ] Add `import { Table } from '@/components/Table'` at the top
- [ ] Convert each markdown table to the Table component
- [ ] Test the page to ensure tables render correctly
- [ ] Check both light and dark modes
- [ ] Verify responsive behavior on mobile devices
