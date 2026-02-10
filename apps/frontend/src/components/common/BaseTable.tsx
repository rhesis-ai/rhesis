import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  Button,
  Collapse,
  CircularProgress,
  useTheme,
} from '@mui/material';
import Link from 'next/link';

interface _AddButtonProps {
  label: string;
  href?: string;
  onClick?: () => void;
}

interface Column {
  id: string;
  label: string;
  render: (row: any, index: number) => React.ReactNode;
}

interface BaseTableProps {
  columns: Column[];
  data: any[];
  title?: string;
  onRowClick?: (row: any) => void;
  actionButtons?: {
    href?: string;
    label: string;
    onClick?: () => void;
    icon?: React.ReactNode;
    variant?: 'text' | 'outlined' | 'contained';
  }[];
  rowHighlight?: {
    [key: number]: {
      color: string;
    };
  };
  expandedRow?: number | null;
  renderExpanded?: (row: any, index: number) => React.ReactNode;
  loading?: boolean;
}

export default function BaseTable({
  columns,
  data,
  title,
  onRowClick,
  actionButtons,
  rowHighlight,
  expandedRow,
  renderExpanded,
  loading = false,
}: BaseTableProps) {
  const theme = useTheme();
  const handleRowClick = (row: any) => {
    if (onRowClick) {
      onRowClick(row);
    }
  };

  return (
    <>
      {(title || actionButtons) && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: title ? 'space-between' : 'flex-end',
            alignItems: 'center',
            mb: 3,
          }}
        >
          {title && (
            <Typography variant="h5" component="h1">
              {title}
            </Typography>
          )}
          {actionButtons && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              {actionButtons.map((button, index) =>
                button.href ? (
                  <Link
                    key={index}
                    href={button.href}
                    style={{ textDecoration: 'none' }}
                  >
                    <Button
                      variant={button.variant || 'contained'}
                      startIcon={button.icon}
                    >
                      {button.label}
                    </Button>
                  </Link>
                ) : (
                  <Button
                    key={index}
                    variant={button.variant || 'contained'}
                    startIcon={button.icon}
                    onClick={button.onClick}
                  >
                    {button.label}
                  </Button>
                )
              )}
            </Box>
          )}
        </Box>
      )}

      <TableContainer
        component={Paper}
        sx={{
          boxShadow: 1,
          borderRadius: theme.shape.borderRadius,
          overflow: 'hidden',
          bgcolor: 'background.paper',
          minHeight: 200,
          position: 'relative',
        }}
      >
        {loading ? (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: 200,
            }}
          >
            <CircularProgress />
          </Box>
        ) : data.length === 0 ? (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: 200,
            }}
          >
            <Typography color="text.secondary">No data available</Typography>
          </Box>
        ) : (
          <Table sx={{ minWidth: 650 }}>
            <TableHead>
              <TableRow sx={{ backgroundColor: 'grey.50' }}>
                {columns.map(column => (
                  <TableCell
                    key={column.id}
                    sx={{ fontWeight: 'bold', color: 'text.primary' }}
                  >
                    {column.label}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((row, index) => (
                <React.Fragment key={index}>
                  <TableRow
                    sx={{
                      '&:nth-of-type(odd)': { backgroundColor: 'grey.50' },
                      '&:hover': {
                        backgroundColor: 'grey.100',
                        cursor: onRowClick ? 'pointer' : 'default',
                      },
                      transition: 'background-color 0.2s',
                      ...(rowHighlight?.[index] && {
                        outline: `2px solid ${rowHighlight[index].color}`,
                        outlineOffset: '-1px',
                      }),
                    }}
                    onClick={() => handleRowClick(row)}
                  >
                    {columns.map(column => (
                      <TableCell key={column.id}>
                        {column.render(row, index)}
                      </TableCell>
                    ))}
                  </TableRow>
                  {renderExpanded && (
                    <TableRow>
                      <TableCell
                        style={{ paddingBottom: 0, paddingTop: 0 }}
                        colSpan={columns.length}
                      >
                        <Collapse
                          in={expandedRow === index}
                          timeout="auto"
                          unmountOnExit
                        >
                          <Box sx={{ py: 2 }}>{renderExpanded(row, index)}</Box>
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        )}
      </TableContainer>
    </>
  );
}
