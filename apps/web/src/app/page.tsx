import { GitBranch } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-md flex-col items-center justify-center py-16 px-8 bg-white dark:bg-zinc-900 shadow-xl rounded-2xl border border-zinc-200 dark:border-zinc-800">
        <div className="flex flex-col items-center gap-2 text-center mb-10">
          <h1 className="text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
            Reponis
          </h1>
          <p className="text-lg text-zinc-500 dark:text-zinc-400">
            Engineering Intelligence Platform
          </p>
        </div>
        
        <a
          className="flex w-full items-center justify-center gap-3 rounded-lg bg-zinc-900 px-5 py-4 text-white font-medium transition-colors hover:bg-zinc-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200 shadow-sm"
          href={process.env.NEXT_PUBLIC_API_URL ? `${process.env.NEXT_PUBLIC_API_URL}/auth/github/login` : "http://localhost:8000/api/v1/auth/github/login"}
        >
          <GitBranch className="w-5 h-5" />
          Continue with GitHub
        </a>
      </main>
    </div>
  );
}
