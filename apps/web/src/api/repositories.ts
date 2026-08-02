import api from '@/lib/axios';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export interface RepositoryAvailable {
  github_repo_id: number;
  owner: string;
  name: string;
  full_name: string;
  visibility: string;
  description?: string;
  language?: string;
  html_url: string;
}

export interface RepositoriesAvailableResponse {
  repositories: RepositoryAvailable[];
}

export interface RepositoryResponse {
  id: string;
  github_repo_id: number;
  full_name: string;
  sync_status: string;
  is_active: boolean;
  connected_at: string;
}

export interface RepositoriesConnectedResponse {
  repositories: RepositoryResponse[];
}

export interface RepositoryCurrentResponse {
  repository: RepositoryResponse | null;
}

export const fetchAvailableRepositories = async (): Promise<RepositoriesAvailableResponse> => {
  const { data } = await api.get<RepositoriesAvailableResponse>('/repositories/available');
  return data;
};

export const fetchConnectedRepositories = async (): Promise<RepositoriesConnectedResponse> => {
  const { data } = await api.get<RepositoriesConnectedResponse>('/repositories/connected');
  return data;
};

export const fetchCurrentRepository = async (): Promise<RepositoryCurrentResponse> => {
  const { data } = await api.get<RepositoryCurrentResponse>('/repositories/current');
  return data;
};

export const connectRepository = async (github_repo_id: number): Promise<RepositoryResponse> => {
  const { data } = await api.post<RepositoryResponse>('/repositories/connect', { github_repo_id });
  return data;
};

export const useAvailableRepositories = () => {
  return useQuery({
    queryKey: ['repositories', 'available'],
    queryFn: fetchAvailableRepositories,
  });
};

export const useConnectedRepositories = () => {
  return useQuery({
    queryKey: ['repositories', 'connected'],
    queryFn: fetchConnectedRepositories,
  });
};

export const useCurrentRepository = () => {
  return useQuery({
    queryKey: ['repositories', 'current'],
    queryFn: fetchCurrentRepository,
  });
};

export const useConnectRepository = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: connectRepository,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories', 'current'] });
      queryClient.invalidateQueries({ queryKey: ['repositories', 'connected'] });
    },
  });
};
