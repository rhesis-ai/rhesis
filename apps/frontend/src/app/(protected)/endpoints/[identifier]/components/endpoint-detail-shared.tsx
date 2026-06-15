'use client';

import React from 'react';
import {
  SmartToyIcon,
  DevicesIcon,
  WebIcon,
  StorageIcon,
  CodeIcon,
  DataObjectIcon,
  CloudIcon,
  AnalyticsIcon,
  ShoppingCartIcon,
  TerminalIcon,
  VideogameAssetIcon,
  ChatIcon,
  PsychologyIcon,
  DashboardIcon,
  SearchIcon,
  AutoFixHighIcon,
  PhoneIphoneIcon,
  SchoolIcon,
  ScienceIcon,
  AccountTreeIcon,
} from '@/components/icons';
import { Project } from '@/utils/api-client/interfaces/project';

export const ENVIRONMENTS = [
  'production',
  'staging',
  'development',
  'local',
] as const;

export const METHODS = ['POST'] as const;

export const TAB_KEYS = [
  'overview',
  'connection',
  'headers',
  'mapping',
  'connection-test',
] as const;
export type EndpointTabKey = (typeof TAB_KEYS)[number];

/** @deprecated Old tab URLs — `mappings` was the former combined test tab */
export const LEGACY_TAB_MAP: Record<string, EndpointTabKey> = {
  mappings: 'connection-test',
};

const ICON_MAP: Record<string, React.ComponentType> = {
  SmartToy: SmartToyIcon,
  Devices: DevicesIcon,
  Web: WebIcon,
  Storage: StorageIcon,
  Code: CodeIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  ShoppingCart: ShoppingCartIcon,
  Terminal: TerminalIcon,
  VideogameAsset: VideogameAssetIcon,
  Chat: ChatIcon,
  Psychology: PsychologyIcon,
  Dashboard: DashboardIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon,
};

export function getProjectIcon(project: Project) {
  if (project?.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }
  return <SmartToyIcon />;
}

export function getEnvironmentChipColor():
  | 'default'
  | 'primary'
  | 'secondary'
  | 'error'
  | 'info'
  | 'success'
  | 'warning' {
  return 'default';
}
