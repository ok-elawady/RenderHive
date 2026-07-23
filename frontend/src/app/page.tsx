"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import { Moon, Plus, Search, Sun } from "lucide-react";
import AgenticLogs from "@/components/dashboard/AgenticLogs";
import HardwareTelemetry from "@/components/dashboard/HardwareTelemetry";
import JobQueue from "@/components/dashboard/JobQueue";
import KpiCards from "@/components/dashboard/KpiCards";
import NewJobModal from "@/components/dashboard/NewJobModal";
import { PageSkeleton } from "@/components/ui/SkeletonLoaders";
import {
  deriveLogsFromJobs,
  deriveTelemetryFromJobs,
  fetchJobs,
  mapBackendJobToRenderJob,
  API_BASE_URL,
} from "@/services/api";
import { useNavigation } from "@/components/common/NavigationProvider";
import { useTheme } from "@/components/common/ThemeProvider";
import type { LogEntry, RenderJob, TelemetryMetrics } from "@/types/dashboard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

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

  const handleJobSubmitted = async (jobName: string): Promise<void> => {
    await refreshJobsData();
    toast.success("Saved Successfully", {
      description: `Job "${jobName}" successfully queued!`,
    });
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

  const renderKpiCards = (): React.ReactNode => (
    <KpiCards activeJobs={activeJobCount} farmEfficiency={farmEfficiency} />
  );

  const renderJobQueue = (): React.ReactNode => (
    <JobQueue
      jobs={jobs}
      searchQuery=""
      onJobRemoved={refreshJobsData}
    />
  );

  const renderDashboardContent = (): React.ReactNode => {
    if (isLoading) {
      return <PageSkeleton />;
    }

    if (activeView === "Active Queue") {
      return <div className="min-h-[520px]">{renderJobQueue()}</div>;
    }

    if (activeView === "Node Pool") {
      return (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <HardwareTelemetry telemetry={telemetry} />
          <Card className="border-border">
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Node Pool Preview
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              <p className="text-sm text-foreground">
                Worker pool metrics are derived from the latest Django job queue
                response until dedicated telemetry endpoints are exposed.
              </p>
            </CardContent>
          </Card>
        </div>
      );
    }

    if (activeView === "AI Rules") {
      return <AgenticLogs logs={logs} searchQuery="" />;
    }

    if (activeView === "Settings") {
      return (
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Platform Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <h2 className="text-xl font-bold text-foreground">
              API base URL: {API_BASE_URL}
            </h2>
          </CardContent>
        </Card>
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

        <AgenticLogs logs={logs} searchQuery="" />
      </>
    );
  };

  return (
    <div className="flex-1 p-6 space-y-6 font-mono">

      {renderDashboardContent()}

      <NewJobModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleJobSubmitted}
      />
    </div>
  );
}
