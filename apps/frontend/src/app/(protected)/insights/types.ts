export interface InsightsFilters {
  months: number;
  endpointId: string;
}

export const DEFAULT_INSIGHTS_FILTERS: InsightsFilters = {
  months: 1,
  endpointId: '',
};
