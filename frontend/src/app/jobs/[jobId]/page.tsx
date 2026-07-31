"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { Pencil, RefreshCw, Trash2, Hash, LayoutList, Server, Folder, Layers, ShieldAlert, CheckCircle2, Clock, PlayCircle, PauseCircle, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/PageHeader";
import { DependencyPanel } from "@/components/dashboard/DependencyPanel";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  abortJob,
  formatApiError,
  getJob,
  getJobLayers,
  updateJob,
  readAuthSession,
  type JobDetail,
  type LayerList,
} from "@/services/api";

const counters: Array<keyof Pick<JobDetail, "ready_tasks" | "running_tasks" | "failed_tasks" | "succeeded_tasks">> = [
  "ready_tasks",
  "running_tasks",
  "failed_tasks",
  "succeeded_tasks",
];

function prettyCounterLabel(key: string): string {
  return key.replace("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function LayerStateBadge({ state }: { state: string }) {
  switch (state) {
    case "FINISHED":
      return (
        <Badge variant="secondary" className="bg-success/15 text-success hover:bg-success/20 gap-1.5 pr-2.5">
          <CheckCircle2 className="size-3.5" /> Finished
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="secondary" className="bg-destructive/15 text-destructive hover:bg-destructive/20 gap-1.5 pr-2.5">
          <XCircle className="size-3.5" /> Failed
        </Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="secondary" className="bg-primary/15 text-primary hover:bg-primary/20 gap-1.5 pr-2.5">
          <PlayCircle className="size-3.5" /> Running
        </Badge>
      );
    case "PAUSED":
      return (
        <Badge variant="secondary" className="gap-1.5 pr-2.5 text-muted-foreground">
          <PauseCircle className="size-3.5" /> Paused
        </Badge>
      );
    case "PENDING":
      return (
        <Badge variant="secondary" className="bg-warning/15 text-warning hover:bg-warning/20 gap-1.5 pr-2.5">
          <Clock className="size-3.5" /> Pending
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className="gap-1.5 pr-2.5 text-muted-foreground">
          <Clock className="size-3.5" /> {state.charAt(0) + state.slice(1).toLowerCase()}
        </Badge>
      );
  }
}

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [layers, setLayers] = useState<LayerList[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isEditOpen, setIsEditOpen] = useState<boolean>(false);
  const [draft, setDraft] = useState({ visible_name: "", priority: 50, max_tasks_per_worker: 0 });

  const session = useMemo(() => readAuthSession(), []);
  const isStaff = session?.user?.isStaff || session?.user?.isSuperuser || false;

  const completedTasks = useMemo(() => (job ? job.succeeded_tasks + job.skipped_tasks : 0), [job]);

  const loadJob = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const [jobData, layerData] = await Promise.all([getJob(jobId), getJobLayers(jobId)]);
      setJob(jobData);
      setLayers(layerData);
      setDraft({
        visible_name: jobData.visible_name,
        priority: jobData.priority,
        max_tasks_per_worker: jobData.max_tasks_per_worker,
      });
    } catch (error) {
      toast.error("Unable to load job", { description: formatApiError(error) });
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadJob();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadJob]);

  const handleDraftChange =
    (key: keyof typeof draft) =>
    (event: ChangeEvent<HTMLInputElement>): void => {
      const value = event.target.value;
      setDraft((current) => ({
        ...current,
        [key]: key === "visible_name" ? value : Number(value),
      }));
    };

  const handleSave = async (): Promise<void> => {
    try {
      await updateJob(jobId, draft);
      toast.success("Job metadata updated");
      setIsEditOpen(false);
      await loadJob();
    } catch (error) {
      toast.error("Update failed", { description: formatApiError(error) });
    }
  };

  const handleAbort = async (): Promise<void> => {
    if (!window.confirm("Abort this job and remove all nested layers and tasks?")) return;

    try {
      await abortJob(jobId);
      toast.success("Job aborted");
      router.push("/jobs");
    } catch (error) {
      toast.error("Abort failed", { description: formatApiError(error) });
    }
  };

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader
        title={job?.visible_name ?? "Loading job..."}
        description={job ? `${job.project} / ${job.department} / ${job.user}` : "Fetching details..."}
        backTo="/jobs"
      >
        <Button variant="outline" onClick={() => void loadJob()} className="gap-2">
          <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          Refresh
        </Button>
        <Button variant="outline" onClick={() => setIsEditOpen(true)} disabled={!job} className="gap-2">
          <Pencil size={14} />
          Edit
        </Button>
        <Button
          variant="outline"
          onClick={() => void handleAbort()}
          disabled={!job}
          className="gap-2 border-destructive/30 text-destructive hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 size={14} />
          Abort
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
          {isLoading || !job ? (
            <Card className="border-border">
              <CardContent className="flex h-56 items-center justify-center text-muted-foreground">
                Loading job detail...
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
                <Card className="border-border md:col-span-1">
                  <CardHeader>
                    <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">State</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Badge
                      variant={job.state === "FAILED" ? "destructive" : job.state === "RUNNING" ? "info" : "secondary"}
                    >
                      {job.state}
                    </Badge>
                    <p className="mt-3 text-xs text-muted-foreground">
                      {completedTasks}/{job.total_tasks} tasks completed
                    </p>
                  </CardContent>
                </Card>

                {counters.map((counter) => (
                  <Card key={counter} className="border-border">
                    <CardHeader>
                      <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
                        {prettyCounterLabel(counter)}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-black text-foreground">{job[counter]}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Job Context Panel */}
              <Card className="border-border">
                <CardHeader className="pb-3 border-b border-border/50">
                  <CardTitle className="flex items-center gap-2 text-sm font-bold">
                    <Server size={16} className="text-info" />
                    Job Context
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 grid grid-cols-2 md:grid-cols-4 gap-y-5 gap-x-6 text-sm">
                  <div>
                    <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Hash size={12} /> System Name
                    </div>
                    <div className="font-medium font-mono text-xs truncate" title={job.name}>
                      {job.name || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <ShieldAlert size={12} /> Priority
                    </div>
                    <div className="font-medium">
                      <Badge variant="secondary" className="rounded-sm px-1.5 py-0 text-xs font-normal">
                        {job.priority}
                      </Badge>
                    </div>
                  </div>
                  <div className="md:col-span-1">
                    <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Folder size={12} /> Log Directory
                    </div>
                    <div className="font-medium truncate text-xs" title={job.log_directory}>
                      {job.log_directory || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Layers size={12} /> Max Tasks / Worker
                    </div>
                    <div className="font-medium">{job.max_tasks_per_worker} tasks</div>
                  </div>
                </CardContent>
              </Card>

              {/* Layers Table */}
              <Card className="border-border p-0 gap-0">
                <CardHeader className="p-4 pb-3 border-b border-border/50">
                  <CardTitle className="flex items-center gap-2 text-sm font-bold">
                    <Layers size={16} className="text-primary" />
                    Execution Layers
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader className="bg-muted/30">
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="pl-6 font-semibold w-[25%]">Name</TableHead>
                        <TableHead className="font-semibold text-center w-[15%]">Type</TableHead>
                        <TableHead className="font-semibold text-center w-[15%]">State</TableHead>
                        <TableHead className="font-semibold text-center w-[20%]">Frame Range</TableHead>
                        <TableHead className="font-semibold text-right pr-6 w-[25%]">Progress</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {layers.map((layer) => (
                        <TableRow key={layer.id} className="hover:bg-muted/40 transition-colors group">
                          <TableCell className="pl-6">
                            <Link
                              href={`/jobs/${job.id}/layers/${layer.id}`}
                              className="font-bold text-primary hover:underline"
                            >
                              {layer.name}
                            </Link>
                          </TableCell>
                          <TableCell className="text-center">{layer.layer_type}</TableCell>
                          <TableCell className="text-center">
                            <LayerStateBadge state={layer.state} />
                          </TableCell>
                          <TableCell className="text-center">{layer.frame_range}</TableCell>
                          <TableCell className="text-right text-muted-foreground pr-6">
                            {layer.succeeded_tasks + layer.skipped_tasks}/{layer.total_tasks}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Dependencies Panel (Full Width Expandable) */}
              <DependencyPanel jobId={job.id} isStaff={isStaff} />
            </>
          )}
        </div>

        <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
          <DialogContent className="border-border bg-surface">
            <DialogHeader>
              <DialogTitle>Edit Job Metadata</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Visible Name</Label>
                <Input value={draft.visible_name} onChange={handleDraftChange("visible_name")} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Input type="number" value={draft.priority} onChange={handleDraftChange("priority")} />
                </div>
                <div className="space-y-2">
                  <Label>Max Tasks / Worker</Label>
                  <Input
                    type="number"
                    value={draft.max_tasks_per_worker}
                    onChange={handleDraftChange("max_tasks_per_worker")}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setIsEditOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={() => void handleSave()}>Save changes</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
