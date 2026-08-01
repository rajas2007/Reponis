"use client";

import { useCurrentUser, useLogout } from "@/api/auth";
import { Loader2, LogOut, GitBranch, User as UserIcon } from "lucide-react";
import Image from "next/image";
import { useEffect } from "react";

export default function DashboardPage() {
  const { data: user, isLoading, isError } = useCurrentUser();
  const logout = useLogout();

  useEffect(() => {
    if (!isLoading && (isError || !user)) {
      if (typeof window !== "undefined") {
        window.location.href = "/";
      }
    }
  }, [isLoading, isError, user]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  if (isError || !user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black text-zinc-900 dark:text-zinc-50 font-sans">
      <header className="flex h-16 items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6">
        <div className="flex items-center gap-2">
          <GitBranch className="w-6 h-6" />
          <span className="text-xl font-bold tracking-tight">Reponis</span>
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

      <main className="mx-auto max-w-7xl p-8">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-2 text-zinc-500 dark:text-zinc-400">
          Welcome back, {user.username}! Your engineering intelligence overview will appear here.
        </p>
        
        {/* Placeholder for future sprint content */}
        <div className="mt-8 rounded-xl border border-dashed border-zinc-300 dark:border-zinc-800 p-12 text-center">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Analytics widgets and repository connections coming soon in Sprint 1.2
          </p>
        </div>
      </main>
    </div>
  );
}
