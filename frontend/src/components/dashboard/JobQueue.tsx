"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { deleteJob, formatApiError } from "@/services/api";
import type { RenderJob } from "@/types/dashboard";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface JobQueueProps {
  jobs: RenderJob[];
  searchQuery: string;
  onJobRemoved: () => Promise<void>;
}


function matchesJobSearch(job: RenderJob, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [job.id, job.displayId, job.user, job.status, job.backendState].some((value) =>
    value.toLowerCase().includes(normalizedQuery),
  );
}

function getStatusBadgeProps(status: RenderJob["status"]): {
  variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info";
  className?: string;
} {
  if (status === "Rendering") {
    return { variant: "info" };
  }
  if (status === "Queued") {
    return { variant: "secondary" };
  }
  if (status === "Completed") {
    return { variant: "success" };
  }
  return { variant: "destructive" };
}

export default function JobQueue({ jobs, searchQuery, onJobRemoved }: JobQueueProps) {
  const router = useRouter();
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
      router.refresh();
      toast.success("Job deleted");
    } catch (error) {
      toast.error("Delete failed", {
        description: formatApiError(error),
      });
    } finally {
      setDeletingJobId(null);
    }
  };

  return (
    <Card className="flex flex-col justify-between h-full border-border">
      <CardHeader>
        <CardTitle className="text-base font-bold text-foreground">Live Job Queue</CardTitle>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col">
        <div className="rounded-lg border border-border overflow-hidden flex-1 flex flex-col">
          <div className="flex-1 overflow-auto">
            <Table>
              <TableHeader className="bg-surface-deep">
                <TableRow>
                  <TableHead className="w-[20%]">Job ID</TableHead>
                  <TableHead className="w-[10%] text-center">Priority</TableHead>
                  <TableHead className="w-[15%] text-center">User</TableHead>
                  <TableHead className="w-[15%] text-center">Status</TableHead>
                  <TableHead className="w-[30%] text-center">Progress</TableHead>
                  <TableHead className="w-[10%] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="text-xs font-mono">
                {filteredJobs.length > 0 ? (
                  filteredJobs.map((job) => (
                    <TableRow key={job.id} className="hover:bg-surface-hover group transition-colors">
                      <TableCell className="font-medium text-foreground group-hover:text-primary transition-colors py-3">
                        <Link
                          className="text-purple-400 transition-all hover:text-purple-300 hover:underline"
                          href={`/jobs/${job.id}`}
                        >
                          {job.displayId}
                        </Link>
                      </TableCell>
                      <TableCell className="text-center font-bold text-foreground">
                        {job.priority}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-center">{job.user}</TableCell>
                      <TableCell className="text-center">
                        <Badge {...getStatusBadgeProps(job.status)}>{job.status}</Badge>
                      </TableCell>
                      <TableCell className="text-center py-3">
                        <div className="flex items-center justify-center gap-3 translate-y-[1px]">
                          <span className="text-muted-foreground w-8 text-right font-medium">{job.progress}%</span>
                          <Progress value={job.progress} className="w-20 h-[6px] rounded-full" />
                          <span className="text-[11px] text-muted-foreground text-left whitespace-nowrap">{job.frameCounts}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right py-3">
                        <Button
                          variant="destructive"
                          size="sm"
                          className="h-7 px-2 text-[10px]"
                          onClick={() => void handleRemoveJob(job.id)}
                          disabled={deletingJobId === job.id}
                          aria-label={`Kill or remove ${job.displayId}`}
                        >
                          <Trash2 size={13} />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow className="hover:bg-transparent border-0">
                    <TableCell colSpan={6} className="h-32 text-center">
                      <div className="flex flex-col items-center justify-center">
                        <Search size={34} className="mb-3 text-primary opacity-25" />
                        <p className="text-sm font-bold text-foreground">No matching active render jobs found</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Try a Job ID, node name, or status keyword.
                        </p>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
