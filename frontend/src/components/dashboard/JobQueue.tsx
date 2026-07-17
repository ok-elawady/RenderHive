"use client";

import { useMemo, useState } from "react";
import { Search, Trash2 } from "lucide-react";
import { deleteJob } from "@/services/api";
import type { JobPriority, RenderJob } from "@/types/dashboard";

interface JobQueueProps {
  jobs: RenderJob[];
  searchQuery: string;
  onJobRemoved: () => Promise<void>;
}

function getPriorityClass(priority: JobPriority): string {
  if (priority === "HIGH") return "text-destructive";
  if (priority === "MED") return "text-warning";
  return "text-muted-foreground";
}

function matchesJobSearch(job: RenderJob, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [job.id, job.displayId, job.node, job.status, job.backendState].some(
    (value) => value.toLowerCase().includes(normalizedQuery),
  );
}

function getJobStatusColor(status: RenderJob["status"]): string {
  if (status === "Rendering") {
    return "text-primary bg-primary/10 border-primary/30";
  }
  if (status === "Queued") {
    return "text-info bg-info/10 border-info/30";
  }
  if (status === "Completed") {
    return "text-success bg-success/10 border-success/30";
  }
  return "text-destructive bg-destructive/10 border-destructive/30";
}

export default function JobQueue({
  jobs,
  searchQuery,
  onJobRemoved,
}: JobQueueProps) {
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null);
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredJobs = useMemo<RenderJob[]>(
    () => jobs.filter((job) => matchesJobSearch(job, normalizedQuery)),
    [jobs, normalizedQuery],
  );

  const handleRemoveJob = async (jobId: string): Promise<void> => {
    setDeletingJobId(jobId);

    try {
      await deleteJob(jobId);
      await onJobRemoved();
    } finally {
      setDeletingJobId(null);
    }
  };

  return (
    <div className="bg-surface border border-border p-6 rounded-lg flex flex-col justify-between h-full shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
      <div>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-base font-bold text-foreground">
            Live Job Queue
          </h3>
          <span className="text-xs font-semibold text-primary">
            {filteredJobs.length} active
          </span>
        </div>

        <div className="overflow-x-auto rounded-lg border border-input">
          <table className="w-full text-left border-collapse">
            <thead className="bg-surface-hover">
              <tr className="border-b border-input text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-3 font-medium">Job ID</th>
                <th className="px-4 py-3 font-medium">Priority</th>
                <th className="px-4 py-3 font-medium">Assigned Node</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Progress</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-input text-xs font-mono">
              {filteredJobs.length > 0 ? (
                filteredJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="bg-surface-deep hover:bg-surface-hover transition-all group"
                  >
                    <td className="px-4 py-4 font-medium text-foreground group-hover:text-primary transition-colors">
                      {job.displayId}
                    </td>
                    <td
                      className={`px-4 py-4 font-bold text-[10px] ${getPriorityClass(job.priority)}`}
                    >
                      {job.priority}
                    </td>
                    <td className="px-4 py-4 text-muted-foreground">
                      {job.node}
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] border ${getJobStatusColor(job.status)}`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <span className="text-muted-foreground w-8 text-right">
                          {job.progress}%
                        </span>
                        <div className="w-20 bg-input h-1 rounded-full overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-primary to-primary/80 h-full transition-all duration-500 shadow-[0_0_10px] shadow-primary/40"
                            style={{ width: `${job.progress}%` }}
                          ></div>
                        </div>
                        <span className="text-[11px] text-muted-foreground w-16 text-left">
                          {job.eta}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => void handleRemoveJob(job.id)}
                        disabled={deletingJobId === job.id}
                        className="inline-flex items-center justify-center rounded-md border border-destructive/30 px-2.5 py-1 text-destructive transition-all hover:bg-destructive/10 disabled:cursor-wait disabled:opacity-60"
                        aria-label={`Kill or remove ${job.displayId}`}
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="bg-surface-deep">
                  <td colSpan={6} className="px-4 py-14">
                    <div className="flex flex-col items-center justify-center text-center">
                      <Search
                        size={34}
                        className="mb-3 text-primary opacity-25"
                      />
                      <p className="text-sm font-bold text-foreground">
                        No matching active render jobs found
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Try a Job ID, node name, or status keyword.
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
