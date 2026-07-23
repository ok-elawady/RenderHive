"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { Pause, Play, RefreshCw, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  deleteJob,
  formatApiError,
  getJobs,
  pauseJob,
  resumeJob,
  type BackendJob,
  type JobFilters,
  type JobStateFilter,
} from "@/services/api";

const jobStates: Array<JobStateFilter | ""> = [
  "",
  "PENDING",
  "RUNNING",
  "PAUSED",
  "FINISHED",
  "FAILED",
];

function getJobBadgeVariant(
  state: BackendJob["state"],
): "secondary" | "destructive" | "success" | "warning" | "info" {
  if (state === "RUNNING") return "info";
  if (state === "FINISHED") return "success";
  if (state === "FAILED") return "destructive";
  if (state === "PAUSED") return "warning";
  return "secondary";
}

export default function JobsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<BackendJob[]>([]);
  const [filters, setFilters] = useState<JobFilters>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [actionJobId, setActionJobId] = useState<string | null>(null);

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter(Boolean).length,
    [filters],
  );

  const fetchData = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      setJobs(await getJobs(filters));
    } catch (error) {
      toast.error("Unable to load jobs", { description: formatApiError(error) });
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchData();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [fetchData]);

  const updateFilter =
    (key: keyof JobFilters) =>
    (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>): void => {
      const value = event.target.value;
      setFilters((current) => ({
        ...current,
        [key]: value || undefined,
      }));
    };

  const handleTransition = async (
    jobId: string,
    action: "pause" | "resume",
  ): Promise<void> => {
    setActionJobId(jobId);
    try {
      if (action === "pause") {
        await pauseJob(jobId);
      } else {
        await resumeJob(jobId);
      }
      toast.success(action === "pause" ? "Job paused" : "Job resumed");
      await fetchData();
    } catch (error) {
      toast.error("Job action failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  const handleRemoveJob = async (jobId: string): Promise<void> => {
    if (!window.confirm("Delete this job and all nested layers and frames?")) return;

    setActionJobId(jobId);
    try {
      await deleteJob(jobId);
      setJobs((currentJobs) => currentJobs.filter((job) => job.id !== jobId));
      toast.success("Job deleted");
      await fetchData();
      router.refresh();
    } catch (error) {
      toast.error("Delete failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  return (
    <div className="h-screen overflow-y-auto bg-background p-6 text-foreground font-mono">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
              RenderHive Queue
            </p>
            <h1 className="mt-1 text-2xl font-black tracking-tight">
              Jobs Dashboard
            </h1>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void fetchData()}>
              <RefreshCw size={15} />
              Refresh
            </Button>
          </div>
        </div>

        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Search size={16} className="text-primary" />
              Filters
              {activeFilterCount > 0 && (
                <Badge variant="info">{activeFilterCount} active</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <Input
              value={filters.project ?? ""}
              onChange={updateFilter("project")}
              placeholder="Project"
            />
            <Input
              value={filters.department ?? ""}
              onChange={updateFilter("department")}
              placeholder="Department"
            />
            <select
              value={filters.state ?? ""}
              onChange={updateFilter("state")}
              className="h-9 rounded-3xl bg-input/50 px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
            >
              {jobStates.map((state) => (
                <option key={state || "all"} value={state}>
                  {state || "All states"}
                </option>
              ))}
            </select>
            <Input
              value={filters.user ?? ""}
              onChange={updateFilter("user")}
              placeholder="User"
            />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-base">Active / Queued Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job</TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="text-right">Frames</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                      Loading jobs...
                    </TableCell>
                  </TableRow>
                ) : jobs.length > 0 ? (
                  jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell>
                        <Link
                          className="font-bold text-purple-400 transition-all hover:text-purple-300 hover:underline"
                          href={`/jobs/${job.id}`}
                        >
                          {job.visible_name || job.name}
                        </Link>
                      </TableCell>
                      <TableCell>{job.project}</TableCell>
                      <TableCell>{job.department}</TableCell>
                      <TableCell>{job.user}</TableCell>
                      <TableCell>
                        <Badge variant={getJobBadgeVariant(job.state)}>{job.state}</Badge>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {job.succeeded_frames + job.skipped_frames}/{job.total_frames}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={actionJobId === job.id || job.state === "PAUSED"}
                            onClick={() => void handleTransition(job.id, "pause")}
                          >
                            <Pause size={13} />
                            Pause
                          </Button>
                          <Button
                            size="sm"
                            disabled={actionJobId === job.id || job.state !== "PAUSED"}
                            onClick={() => void handleTransition(job.id, "resume")}
                          >
                            <Play size={13} />
                            Resume
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={actionJobId === job.id}
                            onClick={() => void handleRemoveJob(job.id)}
                            aria-label={`Delete ${job.visible_name || job.name}`}
                          >
                            <Trash2 size={13} />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                      No jobs match the current filters.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
