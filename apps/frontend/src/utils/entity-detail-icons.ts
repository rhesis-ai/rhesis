import type { SvgIconProps } from '@mui/material/SvgIcon';
import FolderOffOutlinedIcon from '@mui/icons-material/FolderOffOutlined';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import SwapHorizOutlinedIcon from '@mui/icons-material/SwapHorizOutlined';
import {
  AccountTreeIcon,
  BehaviorsIcon,
  BiotechIcon,
  CategoryIcon,
  EndpointsIcon,
  InsertChartIcon,
  KnowledgeIcon,
  PlayArrowIcon,
  ScienceIcon,
  TasksIcon,
  TracesIcon,
} from '@/components/icons';

const RESOLVE_ENTITY_ICONS: Record<
  string,
  React.ComponentType<SvgIconProps>
> = {
  test_set: CategoryIcon,
  test: ScienceIcon,
  test_run: PlayArrowIcon,
  endpoint: EndpointsIcon,
  behavior: BehaviorsIcon,
  metric: InsertChartIcon,
  experiment: BiotechIcon,
  task: TasksIcon,
  source: KnowledgeIcon,
  trace: TracesIcon,
};

export function getResolveEntityIcon(
  tableName: string
): React.ComponentType<SvgIconProps> {
  return RESOLVE_ENTITY_ICONS[tableName] ?? FolderOffOutlinedIcon;
}

export { FolderOffOutlinedIcon, LockOutlinedIcon, SwapHorizOutlinedIcon };
