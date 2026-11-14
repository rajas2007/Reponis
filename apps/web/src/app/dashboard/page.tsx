"use client";

import { useCurrentUser, useLogout } from "@/api/auth";
import { useCurrentRepository } from "@/api/repositories";
import { useWeeklyMetrics, WeeklyMetric } from "@/api/analytics";
import {
  Loader2,
  LogOut,
  GitBranch,
  User as UserIcon,
  GitCommit,
  GitPullRequest,
  Clock,
  Bug,
  AlertCircle,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

export default function DashboardPage() {
  const { data: user, isLoading: isUserLoading, isError: isUserError } = useCurrentUser();
  const logout = useLogout();

  const { data: currentRepoData, isLoading: isRepoLoading } = useCurrentRepository();
  const activeRepo = currentRepoData?.repository;

  const { data: metricsData, isLoading: isMetricsLoading } = useWeeklyMetrics(activeRepo?.id);

  useEffect(() => {
    if (!isUserLoading && (isUserError || !user)) {
      if (typeof window !== "undefined") {
        window.location.href = "/";
      }
    }
  }, [isUserLoading, isUserError, user]);

  if (isUserLoading || isRepoLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  if (isUserError || !user) {
    return null;
  }

  const metrics: WeeklyMetric[] = metricsData?.metrics || [];
  const hasMetrics = metrics.length > 0;

  // Chart data formatting
  const chartData = metrics.map((m) => ({
    week: m.week_start.slice(5), // MM-DD
    commits: m.commit_count ?? 0,
    commitFreq: m.commit_frequency_per_day ?? 0,
    prsOpened: m.prs_opened ?? 0,
    prsMerged: m.prs_merged ?? 0,
    prsClosedUnmerged: m.prs_closed_without_merge ?? 0,
    mergeRate: m.pr_merge_rate !== null ? Math.round(m.pr_merge_rate * 100) : null,
    totalCycleTime: m.cycle_time_total_p50 ?? null,
    timeToFirstReview: m.cycle_time_to_first_review_p50 ?? null,
    reviewToApproval: m.cycle_time_review_to_approval_p50 ?? null,
    approvalToMerge: m.cycle_time_approval_to_merge_p50 ?? null,
    issuesOpened: m.issues_opened ?? 0,
    issuesClosed: m.issues_closed ?? 0,
    bugsOpened: m.bugs_opened ?? 0,
    bugsClosed: m.bugs_closed ?? 0,
  }));

  // Summary stats (from the latest non-empty week or overall recent)
  const latestMetric = metrics[metrics.length - 1];

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black text-zinc-900 dark:text-zinc-50 font-sans">
      <header className="flex h-16 items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6">
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <GitBranch className="w-6 h-6" />
            <span className="text-xl font-bold tracking-tight">Reponis</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm font-medium text-blue-600 dark:text-blue-400">
              Dashboard
            </Link>
            <Link
              href="/repositories"
              className="text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-50 transition-colors"
            >
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

      <main className="mx-auto max-w-7xl p-8 space-y-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Engineering Intelligence Dashboard</h1>
          <p className="mt-2 text-zinc-500 dark:text-zinc-400">
            {activeRepo
              ? `Weekly performance metrics and trends for ${activeRepo.full_name}`
              : "Connect a repository to start tracking metrics and engineering insights."}
          </p>
        </div>

        {!activeRepo && (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-8 text-center">
            <GitBranch className="mx-auto h-12 w-12 text-zinc-400" />
            <h3 className="mt-4 text-lg font-semibold">No active repository connected</h3>
            <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              Please connect and synchronize a repository to see engineering analytics.
            </p>
            <div className="mt-6">
              <Link
                href="/repositories"
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Go to Repositories
              </Link>
            </div>
          </div>
        )}

        {activeRepo && !hasMetrics && !isMetricsLoading && (
          <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-800 bg-white dark:bg-zinc-900/50 p-12 text-center">
            <AlertCircle className="mx-auto h-10 w-10 text-amber-500" />
            <h3 className="mt-4 text-lg font-semibold">Metrics not yet computed</h3>
            <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              Trigger a repository synchronization in the Repositories section. Once the sync completes, weekly metrics will be generated automatically.
            </p>
            <div className="mt-6">
              <Link
                href="/repositories"
                className="inline-flex items-center gap-2 rounded-md bg-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 text-white px-4 py-2 text-sm font-medium hover:opacity-90"
              >
                View Sync Status
              </Link>
            </div>
          </div>
        )}

        {activeRepo && hasMetrics && (
          <>
            {/* Quick summary stat cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Current Week Commits</span>
                  <GitCommit className="h-5 w-5 text-blue-500" />
                </div>
                <div className="mt-2 text-2xl font-bold">{latestMetric?.commit_count ?? 0}</div>
                <div className="mt-1 text-xs text-zinc-500">
                  {latestMetric?.commit_frequency_per_day ?? 0} commits / day
                </div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">PRs Merged (This Week)</span>
                  <GitPullRequest className="h-5 w-5 text-green-500" />
                </div>
                <div className="mt-2 text-2xl font-bold">{latestMetric?.prs_merged ?? 0}</div>
                <div className="mt-1 text-xs text-zinc-500">
                  Merge Rate: {latestMetric?.pr_merge_rate !== null ? `${Math.round((latestMetric?.pr_merge_rate ?? 0) * 100)}%` : "N/A"}
                </div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">P50 Total Cycle Time</span>
                  <Clock className="h-5 w-5 text-purple-500" />
                </div>
                <div className="mt-2 text-2xl font-bold">
                  {latestMetric?.cycle_time_total_p50 !== null ? `${latestMetric?.cycle_time_total_p50}h` : "N/A"}
                </div>
                <div className="mt-1 text-xs text-zinc-500">
                  First review: {latestMetric?.cycle_time_to_first_review_p50 !== null ? `${latestMetric?.cycle_time_to_first_review_p50}h` : "N/A"}
                </div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Active Contributors</span>
                  <Bug className="h-5 w-5 text-amber-500" />
                </div>
                <div className="mt-2 text-2xl font-bold">{latestMetric?.active_contributors ?? 0}</div>
                <div className="mt-1 text-xs text-zinc-500">
                  Bugs closed: {latestMetric?.bugs_closed ?? 0}
                </div>
              </div>
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* PR Cycle Time Stages (P50 hours) */}
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <h3 className="text-base font-semibold">PR Cycle Time Stages (P50 Hours)</h3>
                <p className="text-xs text-zinc-500 mt-1 mb-4">
                  Median hours to first review, approval, and merge for merged PRs
                </p>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="week" />
                      <YAxis unit="h" />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="totalCycleTime" name="Total Cycle" stroke="#8b5cf6" strokeWidth={2} dot={false} connectNulls />
                      <Line type="monotone" dataKey="timeToFirstReview" name="To 1st Review" stroke="#3b82f6" strokeWidth={2} dot={false} connectNulls />
                      <Line type="monotone" dataKey="reviewToApproval" name="Review to Approval" stroke="#10b981" strokeWidth={2} dot={false} connectNulls />
                      <Line type="monotone" dataKey="approvalToMerge" name="Approval to Merge" stroke="#f59e0b" strokeWidth={2} dot={false} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* PR Throughput & Merge Rate */}
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <h3 className="text-base font-semibold">Pull Request Throughput</h3>
                <p className="text-xs text-zinc-500 mt-1 mb-4">Weekly volume of opened, merged, and closed PRs</p>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="week" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="prsOpened" name="Opened" fill="#60a5fa" />
                      <Bar dataKey="prsMerged" name="Merged" fill="#34d399" />
                      <Bar dataKey="prsClosedUnmerged" name="Closed Unmerged" fill="#f87171" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Commit Frequency & Volume */}
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <h3 className="text-base font-semibold">Commit Activity</h3>
                <p className="text-xs text-zinc-500 mt-1 mb-4">Weekly commit count and daily average frequency</p>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="week" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="commits" name="Commits" stroke="#2563eb" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="commitFreq" name="Commits / Day" stroke="#06b6d4" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Issue & Bug Throughput */}
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <h3 className="text-base font-semibold">Issue & Bug Throughput</h3>
                <p className="text-xs text-zinc-500 mt-1 mb-4">Weekly opened vs closed issues and bugs</p>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="week" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="issuesOpened" name="Issues Opened" fill="#94a3b8" />
                      <Bar dataKey="issuesClosed" name="Issues Closed" fill="#64748b" />
                      <Bar dataKey="bugsOpened" name="Bugs Opened" fill="#f43f5e" />
                      <Bar dataKey="bugsClosed" name="Bugs Closed" fill="#14b8a6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
