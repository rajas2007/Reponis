import api from '@/lib/axios';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export type SyncStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface ProgressData {
  stage: string;
  current_page: number;
  total_pages: number;
  commits: number;
  pull_requests: number;
  issues: number;
  message?: string | null;
  resume_at?: string | null;
}

export interface SyncJobResponse {
  id: string;
  status: SyncStatus;
  progress_data: ProgressData;
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
}

export const startSync = async (): Promise<SyncJobResponse> => {
  const { data } = await api.post<SyncJobResponse>('/sync/start');
  return data;
};

export const fetchSyncJob = async (jobId: string): Promise<SyncJobResponse> => {
  const { data } = await api.get<SyncJobResponse>(`/sync/${jobId}`);
  return data;
};

export const fetchSyncHistory = async (): Promise<SyncJobResponse[]> => {
  const { data } = await api.get<SyncJobResponse[]>('/sync/history');
  return data;
};

export const useStartSync = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: startSync,
    onSuccess: (data) => {
      queryClient.setQueryData(['sync', 'currentJob'], data);
      queryClient.invalidateQueries({ queryKey: ['sync', 'history'] });
    },
  });
};

export const useSyncJob = (jobId: string | null) => {
  return useQuery({
    queryKey: ['sync', 'job', jobId],
    queryFn: () => fetchSyncJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'queued' || data.status === 'running')) {
        return 3000; // Poll every 3 seconds while active
      }
      return false; // Stop polling
    },
  });
};

export const useSyncHistory = () => {
  return useQuery({
    queryKey: ['sync', 'history'],
    queryFn: fetchSyncHistory,
  });
};
