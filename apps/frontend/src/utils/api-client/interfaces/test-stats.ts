import { UUID } from 'crypto';

export interface TestStats {
  total: number;
  by_behavior?: {
    id: UUID;
    name: string;
    count: number;
  }[];
  by_status?: {
    id: UUID;
    name: string;
    count: number;
  }[];
  by_topic?: {
    id: UUID;
    name: string;
    count: number;
  }[];
} 