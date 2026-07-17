"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import { CheckCircle2, Moon, Plus, Search, Sun } from "lucide-react";
import AgenticLogs from "@/components/dashboard/AgenticLogs";
import HardwareTelemetry from "@/components/dashboard/HardwareTelemetry";
import JobQueue from "@/components/dashboard/JobQueue";
import KpiCards from "@/components/dashboard/KpiCards";
import NewJobModal from "@/components/dashboard/NewJobModal";
import { JobQueueSkeleton, KpiCardsSkeleton } from "@/components/ui/SkeletonLoaders";
import {
  deriveLogsFromJobs,
  deriveTelemetryFromJobs,
  fetchJobs,
  mapBackendJobToRenderJob,
} from "@/services/api";
import { useNavigation } from "@/components/common/NavigationProvider";
import { useTheme } from "@/components/common/ThemeProvider";
import type { LogEntry, RenderJob, TelemetryMetrics } from "@/types/dashboard";

interface ToastState {
  show: boolean;
  message: string;
}

const emptyTelemetry: TelemetryMetrics = {
  vramUsage: 0,
  cpuLoad: 0,
  points: [],
};

function getFarmEfficiency(jobs: RenderJob[]): number {
  if (jobs.length === 0) return 0;

  const failedJobs = jobs.filter((job) => job.status === "Failed").length;
  const completedOrActiveJobs = jobs.filter(
    (job) => job.status === "Completed" || job.status === "Rendering",
  ).length;

  return Math.round(
    ((completedOrActiveJobs + (jobs.length - failedJobs)) / (jobs.length * 2)) *
      100,
  );
}

export default function DashboardPage() {
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [toast, setToast] = useState<ToastState>({ show: false, message: "" });
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [jobs, setJobs] = useState<RenderJob[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryMetrics>(emptyTelemetry);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const initialFetchTimerRef = useRef<number | null>(null);
  const pollingTimerRef = useRef<number | null>(null);
  const { activeView } = useNavigation();
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  const activeJobCount = useMemo<number>(
    () => jobs.filter((job) => job.status === "Rendering").length,
    [jobs],
  );

  const farmEfficiency = useMemo<number>(() => getFarmEfficiency(jobs), [jobs]);

  const fetchJobsData = useCallback(async (): Promise<void> => {
    const backendJobs = await fetchJobs();
    const mappedJobs = backendJobs.map(mapBackendJobToRenderJob);

    setJobs(mappedJobs);
    setLogs(deriveLogsFromJobs(mappedJobs));
    setTelemetry(deriveTelemetryFromJobs(mappedJobs));
    setIsLoading(false);
  }, []);

  const refreshJobsData = useCallback(async (): Promise<void> => {
    await fetchJobsData();
  }, [fetchJobsData]);

  const showSuccessToast = (jobName: string): void => {
    setToast({ show: true, message: `Job "${jobName}" successfully queued!` });
  };

  const handleJobSubmitted = async (jobName: string): Promise<void> => {
    await refreshJobsData();
    showSuccessToast(jobName);
  };

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setSearchQuery(event.target.value);
  };

  useEffect(() => {
    initialFetchTimerRef.current = window.setTimeout(() => {
      void fetchJobsData().catch(() => {
        setJobs([]);
        setLogs([]);
        setTelemetry(emptyTelemetry);
        setIsLoading(false);
      });
    }, 0);

    pollingTimerRef.current = window.setInterval(() => {
      void fetchJobsData().catch(() => {
        setJobs([]);
        setLogs([]);
        setTelemetry(emptyTelemetry);
        setIsLoading(false);
      });
    }, 7000);

    return () => {
      if (initialFetchTimerRef.current !== null) {
        window.clearTimeout(initialFetchTimerRef.current);
      }

      if (pollingTimerRef.current !== null) {
        window.clearInterval(pollingTimerRef.current);
      }
    };
  }, [fetchJobsData]);

  useEffect(() => {
    if (toast.show) {
      const timer = window.setTimeout(() => {
        setToast({ show: false, message: "" });
      }, 4000);
      return () => window.clearTimeout(timer);
    }

    return undefined;
  }, [toast.show]);

  const renderKpiCards = (): React.ReactNode =>
    isLoading ? (
      <KpiCardsSkeleton />
    ) : (
      <KpiCards activeJobs={activeJobCount} farmEfficiency={farmEfficiency} />
    );

  const renderJobQueue = (): React.ReactNode =>
    isLoading ? (
      <JobQueueSkeleton />
    ) : (
      <JobQueue
        jobs={jobs}
        searchQuery={searchQuery}
        onJobRemoved={refreshJobsData}
      />
    );

  const renderDashboardContent = (): React.ReactNode => {
    if (activeView === "Active Queue") {
      return <div className="min-h-[520px]">{renderJobQueue()}</div>;
    }

    if (activeView === "Node Pool") {
      return (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <HardwareTelemetry telemetry={telemetry} />
          <div className="bg-surface border border-border p-6 rounded-lg shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Node Pool Preview
            </p>
            <p className="mt-3 text-sm text-foreground">
              Worker pool metrics are derived from the latest Django job queue
              response until dedicated telemetry endpoints are exposed.
            </p>
          </div>
        </div>
      );
    }

    if (activeView === "AI Rules") {
      return <AgenticLogs logs={logs} searchQuery={searchQuery} />;
    }

    if (activeView === "Settings") {
      return (
        <div className="bg-surface border border-border p-8 rounded-lg shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Platform Settings
          </p>
          <h2 className="mt-3 text-xl font-bold text-foreground">
            API base URL: http://127.0.0.1:8000/api
          </h2>
        </div>
      );
    }

    return (
      <>
        {renderKpiCards()}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">{renderJobQueue()}</div>
          <div>
            <HardwareTelemetry telemetry={telemetry} />
          </div>
        </div>

        <AgenticLogs logs={logs} searchQuery={searchQuery} />
      </>
    );
  };

  return (
    <div className="p-8 space-y-6 overflow-y-auto h-screen bg-background text-foreground w-full font-mono">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface border border-border p-4 rounded-lg shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.25)]">
        <div className="flex items-center gap-6 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse"></span>
            API:{" "}
            <span className="text-foreground">
              localhost:8000
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#9E8EFF]"></span>
            Polling:{" "}
            <span className="text-foreground">7s</span>
          </div>
        </div>

        <div className="relative flex-1 max-w-md mx-0 md:mx-6">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            size={16}
          />
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="Search nodes, jobs, logs..."
            className="w-full bg-background border border-border rounded-lg pl-10 pr-4 py-2 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-primary focus:shadow-[0_0_10px] focus:shadow-primary/30"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            className="group flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface text-primary shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-surface-hover hover:shadow-[0_0_16px] hover:shadow-primary/22 active:scale-95 cursor-pointer"
          >
            {isDark ? (
              <Sun
                key="sun"
                size={17}
                className="transition-transform duration-500 group-hover:rotate-45 group-active:scale-90"
              />
            ) : (
              <Moon
                key="moon"
                size={17}
                className="transition-transform duration-500 group-hover:-rotate-12 group-active:scale-90"
              />
            )}
          </button>

          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-primary hover:bg-primary/90 active:bg-primary/80 text-primary-foreground text-sm px-4 py-2 rounded-lg font-bold shadow-lg shadow-primary/30 transition-all cursor-pointer"
          >
            <Plus size={16} />
            New Job
          </button>
        </div>
      </header>

      {renderDashboardContent()}

      <NewJobModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleJobSubmitted}
      />

      {toast.show && (
        <div className="fixed top-6 right-6 z-50 flex items-center gap-3 bg-success/10 border border-success/30 backdrop-blur-md px-5 py-3.5 rounded-lg shadow-xl shadow-black/20 dark:shadow-black/40 border-l-4 border-l-success">
          <CheckCircle2 className="text-success shrink-0" size={18} />
          <div className="text-xs">
            <p className="text-success font-bold">Saved Successfully</p>
            <p className="text-foreground mt-0.5">
              {toast.message}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
