import api from '@/lib/axios';
import { useQuery } from '@tanstack/react-query';

export interface WeeklyMetric {
  week_start: string;
  commit_count: number | null;
  commit_frequency_per_day: number | null;
  active_contributors: number | null;
  prs_opened: number | null;
  prs_merged: number | null;
  prs_closed_without_merge: number | null;
  pr_merge_rate: number | null;
  cycle_time_total_p50: number | null;
  cycle_time_to_first_review_p50: number | null;
  cycle_time_review_to_approval_p50: number | null;
  cycle_time_approval_to_merge_p50: number | null;
  issues_opened: number | null;
  issues_closed: number | null;
  bugs_opened: number | null;
  bugs_closed: number | null;
  computed_at: string;
}

export interface WeeklyMetricsResponse {
  repository_id: string;
  metrics: WeeklyMetric[];
}

export const fetchWeeklyMetrics = async (
  repositoryId: string
): Promise<WeeklyMetricsResponse> => {
  const { data } = await api.get<WeeklyMetricsResponse>(
    `/analytics/repositories/${repositoryId}/weekly`
  );
  return data;
};

export const useWeeklyMetrics = (repositoryId: string | null | undefined) => {
  return useQuery({
    queryKey: ['analytics', 'weekly', repositoryId],
    queryFn: () => fetchWeeklyMetrics(repositoryId!),
    enabled: !!repositoryId,
  });
};
