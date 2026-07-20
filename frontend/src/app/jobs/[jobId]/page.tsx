"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { ArrowLeft, Pencil, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  abortJob,
  formatApiError,
  getJob,
  getJobLayers,
  updateJob,
  type JobDetail,
  type LayerList,
} from "@/services/api";

const counters: Array<keyof Pick<
  JobDetail,
  "ready_frames" | "running_frames" | "failed_frames" | "succeeded_frames"
>> = ["ready_frames", "running_frames", "failed_frames", "succeeded_frames"];

function prettyCounterLabel(key: string): string {
  return key.replace("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getLayerBadgeVariant(
  state: LayerList["state"],
): "secondary" | "destructive" | "success" | "warning" | "info" {
  if (state === "RUNNING") return "info";
  if (state === "FINISHED") return "success";
  if (state === "FAILED") return "destructive";
  if (state === "PAUSED") return "warning";
  return "secondary";
}

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [layers, setLayers] = useState<LayerList[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isEditOpen, setIsEditOpen] = useState<boolean>(false);
  const [draft, setDraft] = useState({ visible_name: "", priority: 50, max_frames_per_worker: 0 });

  const completedFrames = useMemo(
    () => (job ? job.succeeded_frames + job.skipped_frames : 0),
    [job],
  );

  const loadJob = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const [jobData, layerData] = await Promise.all([
        getJob(jobId),
        getJobLayers(jobId),
      ]);
      setJob(jobData);
      setLayers(layerData);
      setDraft({
        visible_name: jobData.visible_name,
        priority: jobData.priority,
        max_frames_per_worker: jobData.max_frames_per_worker,
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
    if (!window.confirm("Abort this job and remove all nested layers and frames?")) return;

    try {
      await abortJob(jobId);
      toast.success("Job aborted");
      router.push("/jobs");
    } catch (error) {
      toast.error("Abort failed", { description: formatApiError(error) });
    }
  };

  return (
    <div className="h-screen overflow-y-auto bg-background p-6 text-foreground font-mono">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <Button nativeButton={false} variant="ghost" size="sm" render={<Link href="/jobs" />}>
              <ArrowLeft size={14} />
              Back to jobs
            </Button>
            <h1 className="mt-3 text-2xl font-black tracking-tight">
              {job?.visible_name ?? "Loading job..."}
            </h1>
            {job && (
              <p className="mt-1 text-sm text-muted-foreground">
                {job.project} / {job.department} / {job.user}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void loadJob()}>
              <RefreshCw size={15} />
              Refresh
            </Button>
            <Button variant="outline" onClick={() => setIsEditOpen(true)} disabled={!job}>
              <Pencil size={15} />
              Edit
            </Button>
            <Button variant="destructive" onClick={() => void handleAbort()} disabled={!job}>
              <Trash2 size={15} />
              Abort
            </Button>
          </div>
        </div>

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
                  <Badge variant={job.state === "FAILED" ? "destructive" : job.state === "RUNNING" ? "info" : "secondary"}>
                    {job.state}
                  </Badge>
                  <p className="mt-3 text-xs text-muted-foreground">
                    {completedFrames}/{job.total_frames} frames completed
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

            <Tabs defaultValue="layers">
              <TabsList>
                <TabsTrigger value="layers">Layers</TabsTrigger>
                <TabsTrigger value="metadata">Metadata</TabsTrigger>
              </TabsList>
              <TabsContent value="layers">
                <Card className="border-border">
                  <CardHeader>
                    <CardTitle className="text-base">Nested Layers</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>State</TableHead>
                          <TableHead>Frame Range</TableHead>
                          <TableHead className="text-right">Progress</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {layers.map((layer) => (
                          <TableRow key={layer.id}>
                            <TableCell>
                              <Link
                                href={`/jobs/${job.id}/layers/${layer.id}`}
                                className="font-bold text-primary hover:underline"
                              >
                                {layer.name}
                              </Link>
                            </TableCell>
                            <TableCell>{layer.layer_type}</TableCell>
                            <TableCell>
                              <Badge variant={getLayerBadgeVariant(layer.state)}>{layer.state}</Badge>
                            </TableCell>
                            <TableCell>{layer.frame_range}</TableCell>
                            <TableCell className="text-right text-muted-foreground">
                              {layer.succeeded_frames + layer.skipped_frames}/{layer.total_frames}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="metadata">
                <Card className="border-border">
                  <CardContent className="grid grid-cols-1 gap-4 p-6 md:grid-cols-2">
                    <p><span className="text-muted-foreground">System name:</span> {job.name}</p>
                    <p><span className="text-muted-foreground">Priority:</span> {job.priority}</p>
                    <p><span className="text-muted-foreground">Log directory:</span> {job.log_directory}</p>
                    <p><span className="text-muted-foreground">Max frames / worker:</span> {job.max_frames_per_worker}</p>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
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
                <Label>Max Frames / Worker</Label>
                <Input
                  type="number"
                  value={draft.max_frames_per_worker}
                  onChange={handleDraftChange("max_frames_per_worker")}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsEditOpen(false)}>Cancel</Button>
              <Button onClick={() => void handleSave()}>Save changes</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
