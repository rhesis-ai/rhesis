import { Box } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import GridBadge from '@/components/common/GridBadge';
import TagLabel from '@/components/common/Tag';
import {
  getTestContentValue,
  renderTestContentCell,
} from '@/app/(protected)/tests/components/test-grid-helpers';
import { isMultiTurnTest } from '@/constants/test-types';
import type { Tag } from '@/utils/api-client/interfaces/tag';

export function getTestSetTestColumns(testSetType?: string): GridColDef[] {
  return [
    {
      field: 'prompt.content',
      headerName: isMultiTurnTest(testSetType) ? 'Goal' : 'Content',
      flex: 3,
      minWidth: 200,
      valueGetter: getTestContentValue,
      renderCell: renderTestContentCell,
    },
    {
      field: 'behavior',
      headerName: 'Behavior',
      flex: 1,
      minWidth: 120,
      renderCell: params => {
        const behaviorName = params.row.behavior?.name;
        if (!behaviorName) return null;
        return <GridBadge label={behaviorName} />;
      },
    },
    {
      field: 'topic',
      headerName: 'Topic',
      flex: 1,
      minWidth: 120,
      renderCell: params => {
        const topicName = params.row.topic?.name;
        if (!topicName) return null;
        return <GridBadge label={topicName} />;
      },
    },
    {
      field: 'category',
      headerName: 'Category',
      flex: 1,
      minWidth: 120,
      renderCell: params => {
        const categoryName = params.row.category?.name;
        if (!categoryName) return null;
        return <GridBadge label={categoryName} />;
      },
    },
    {
      field: 'test_type.type_value',
      headerName: 'Test Type',
      flex: 1,
      minWidth: 120,
      valueGetter: (_value, row) => row.test_type?.type_value || '',
      renderCell: params => {
        const testType = params.row.test_type?.type_value;
        if (!testType) return null;
        return <GridBadge label={testType} />;
      },
    },
    {
      field: 'tags',
      headerName: 'Tags',
      flex: 1.5,
      minWidth: 140,
      sortable: false,
      renderCell: params => {
        const test = params.row;
        if (!test.tags || test.tags.length === 0) {
          return null;
        }

        const validTags = test.tags.filter(
          (tag: Tag) => tag && tag.id && tag.name
        );

        return (
          <Box
            sx={{
              display: 'flex',
              gap: 0.5,
              flexWrap: 'nowrap',
              overflow: 'hidden',
            }}
          >
            {validTags.slice(0, 2).map((tag: Tag) => (
              <TagLabel key={tag.id} label={tag.name} />
            ))}
            {validTags.length > 2 && (
              <TagLabel label={`+${validTags.length - 2}`} />
            )}
          </Box>
        );
      },
    },
  ];
}
