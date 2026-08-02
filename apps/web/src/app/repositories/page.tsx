"use client";

import { useCurrentUser, useLogout } from "@/api/auth";
import { 
  useAvailableRepositories, 
  useCurrentRepository, 
  useConnectRepository 
} from "@/api/repositories";
import { Loader2, LogOut, GitBranch, User as UserIcon, CheckCircle2, Plus } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";

export default function RepositoriesPage() {
  const { data: user, isLoading: isUserLoading, isError: isUserError } = useCurrentUser();
  const logout = useLogout();
  
  const { data: currentRepoData, isLoading: isCurrentLoading } = useCurrentRepository();
  const { data: availableReposData, isLoading: isAvailableLoading } = useAvailableRepositories();
  const connect = useConnectRepository();

  useEffect(() => {
    if (!isUserLoading && (isUserError || !user)) {
      if (typeof window !== "undefined") {
        window.location.href = "/";
      }
    }
  }, [isUserLoading, isUserError, user]);

  if (isUserLoading || isCurrentLoading || isAvailableLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  if (isUserError || !user) {
    return null;
  }

  const currentRepo = currentRepoData?.repository;
  const availableRepos = availableReposData?.repositories || [];

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black text-zinc-900 dark:text-zinc-50 font-sans">
      <header className="flex h-16 items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6">
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <GitBranch className="w-6 h-6" />
            <span className="text-xl font-bold tracking-tight">Reponis</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-50 transition-colors">
              Dashboard
            </Link>
            <Link href="/repositories" className="text-sm font-medium text-blue-600 dark:text-blue-400">
              Repositories
            </Link>
          </nav>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            {user.avatar_url ? (
              <Image 
                src={user.avatar_url} 
                alt="Avatar" 
                width={32} 
                height={32} 
                className="rounded-full ring-2 ring-zinc-200 dark:ring-zinc-800"
              />
            ) : (
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-200 dark:bg-zinc-800">
                <UserIcon className="w-4 h-4 text-zinc-500" />
              </div>
            )}
            <span className="text-sm font-medium">{user.username}</span>
          </div>
          
          <button
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl p-8">
        <h1 className="text-3xl font-bold tracking-tight mb-8">Repositories</h1>
        
        {/* Current Repository */}
        <div className="mb-12">
          <h2 className="text-xl font-semibold mb-4">Active Repository</h2>
          {currentRepo ? (
            <div className="rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/20 p-6 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <GitBranch className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  <a href={`https://github.com/${currentRepo.full_name}`} target="_blank" rel="noreferrer" className="text-lg font-medium text-blue-700 dark:text-blue-300 hover:underline">
                    {currentRepo.full_name}
                  </a>
                </div>
                <div className="text-sm text-blue-600/80 dark:text-blue-400/80 flex items-center gap-2">
                  <span className="inline-flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Connected
                  </span>
                  &bull;
                  <span>Status: {currentRepo.sync_status}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-800 p-8 text-center bg-white dark:bg-zinc-900">
              <p className="text-zinc-500 dark:text-zinc-400">
                You have not connected a repository yet. Please select one from below.
              </p>
            </div>
          )}
        </div>

        {/* Available Repositories */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Available Repositories</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {availableRepos.map((repo) => (
              <div 
                key={repo.github_repo_id} 
                className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 flex flex-col justify-between transition-shadow hover:shadow-md"
              >
                <div>
                  <div className="flex items-start justify-between mb-2">
                    <a href={repo.html_url} target="_blank" rel="noreferrer" className="font-semibold text-lg hover:text-blue-600 dark:hover:text-blue-400 transition-colors line-clamp-1">
                      {repo.full_name}
                    </a>
                    <span className="inline-flex items-center rounded-full bg-zinc-100 dark:bg-zinc-800 px-2 py-1 text-xs font-medium text-zinc-600 dark:text-zinc-300">
                      {repo.visibility}
                    </span>
                  </div>
                  {repo.description && (
                    <p className="text-sm text-zinc-500 dark:text-zinc-400 line-clamp-2 mb-4">
                      {repo.description}
                    </p>
                  )}
                  {repo.language && (
                    <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-4">
                      {repo.language}
                    </div>
                  )}
                </div>
                
                <button
                  onClick={() => connect.mutate(repo.github_repo_id)}
                  disabled={connect.isPending || currentRepo?.github_repo_id === repo.github_repo_id}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 dark:bg-zinc-100 px-4 py-2 text-sm font-medium text-white dark:text-black transition-colors hover:bg-zinc-800 dark:hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {currentRepo?.github_repo_id === repo.github_repo_id ? (
                    <>
                      <CheckCircle2 className="w-4 h-4" /> Active
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" /> Connect
                    </>
                  )}
                </button>
              </div>
            ))}
            {availableRepos.length === 0 && (
              <div className="col-span-full rounded-xl border border-dashed border-zinc-300 dark:border-zinc-800 p-12 text-center bg-white dark:bg-zinc-900">
                <p className="text-zinc-500 dark:text-zinc-400">
                  No repositories found with pull access.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
