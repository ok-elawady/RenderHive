"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createJob, formatApiError } from "@/services/api";
import type { components } from "@/types/schema";

type CreateJobPayload = components["schemas"]["JobCreate"];
type LayerCreatePayload = components["schemas"]["LayerCreate"];

interface JobFormState {
  project: string;
  department: string;
  logDirectory: string;
}

interface RenderLayerForm {
  id: string;
  name: string;
  command: string;
  frameRange: string;
}

const departmentOptions = ["lighting", "fx", "comp", "td"];

function createLayerDraft(index: number): RenderLayerForm {
  return {
    id: `layer-${Date.now()}-${index}`,
    name: index === 0 ? "beauty" : `layer_${index + 1}`,
    command: "hython render.py --frames 1-100",
    frameRange: "1-100",
  };
}

function buildLayerPayload(layer: RenderLayerForm): LayerCreatePayload {
  return {
    name: layer.name.trim(),
    layer_type: "RENDER",
    command: layer.command.trim(),
    frame_range: layer.frameRange.trim(),
    chunk_size: 1,
    min_cores: 1,
    min_memory_mb: 4096,
    min_gpus: 0,
    max_retries: 3,
    tags: [],
    scene_path: "",
    scene_info: {},
    env: {},
  };
}

export default function SubmitJobPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [job, setJob] = useState<JobFormState>({
    project: "test",
    department: "lighting",
    logDirectory: "/mnt/render/logs",
  });
  const [layers, setLayers] = useState<RenderLayerForm[]>([createLayerDraft(0)]);

  const updateJob =
    (key: keyof JobFormState) =>
    (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>): void => {
      setJob((current) => ({
        ...current,
        [key]: event.target.value,
      }));
    };

  const updateLayer =
    (index: number, key: keyof Omit<RenderLayerForm, "id">) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>): void => {
      setLayers((currentLayers) =>
        currentLayers.map((layer, layerIndex) =>
          layerIndex === index
            ? {
                ...layer,
                [key]: event.target.value,
              }
            : layer,
        ),
      );
    };

  const addLayer = (): void => {
    setLayers((currentLayers) => [
      ...currentLayers,
      createLayerDraft(currentLayers.length),
    ]);
  };

  const removeLayer = (layerId: string): void => {
    setLayers((currentLayers) =>
      currentLayers.length === 1
        ? currentLayers
        : currentLayers.filter((layer) => layer.id !== layerId),
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setIsSubmitting(true);

    const project = job.project.trim();
    const department = job.department.trim();
    const payload: CreateJobPayload = {
      visible_name: `${project}_${department}_render`,
      project,
      department,
      user: "saif",
      priority: 50,
      log_directory: job.logDirectory.trim(),
      max_frames_per_worker: 0,
      layers: layers.map(buildLayerPayload),
    };

    try {
      await createJob(payload);
      toast.success("Job submitted", {
        description: `${payload.project} / ${payload.department} is now in the active queue.`,
      });
      router.push("/jobs");
      router.refresh();
    } catch (error) {
      toast.error("Submission failed", { description: formatApiError(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="h-screen overflow-y-auto bg-background p-6 text-foreground font-mono">
      <form onSubmit={handleSubmit} className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <Button
              nativeButton={false}
              variant="ghost"
              size="sm"
              render={<Link href="/jobs" />}
            >
              <ArrowLeft size={14} />
              Back to jobs
            </Button>
            <h1 className="mt-3 text-2xl font-black tracking-tight">
              Submit Render Job
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Configure the job envelope, then add one or more executable render layers.
            </p>
          </div>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Submitting..." : "Submit Job"}
          </Button>
        </div>

        <Card className="border-border bg-card/95 shadow-xl shadow-black/5">
          <CardHeader className="border-b border-border">
            <CardTitle className="text-base">Job Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-8 p-6">
            <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="project">Project Name</Label>
                <Input
                  id="project"
                  value={job.project}
                  onChange={updateJob("project")}
                  placeholder="test"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="department">Department</Label>
                <select
                  id="department"
                  value={job.department}
                  onChange={updateJob("department")}
                  className="h-9 w-full rounded-lg border border-input bg-input/50 px-3 text-sm outline-none transition-all focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
                  required
                >
                  {departmentOptions.map((department) => (
                    <option key={department} value={department}>
                      {department}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="logDirectory">Log Directory</Label>
                <Input
                  id="logDirectory"
                  value={job.logDirectory}
                  onChange={updateJob("logDirectory")}
                  placeholder="/mnt/render/logs"
                  required
                />
              </div>
            </section>

            <section className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-sm font-black uppercase tracking-wide">
                    Dynamic Render Layers
                  </h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Each layer becomes a nested execution group under this job.
                  </p>
                </div>
                <Button type="button" variant="outline" onClick={addLayer}>
                  <Plus size={15} />
                  Add Layer
                </Button>
              </div>

              <div className="space-y-3">
                {layers.map((layer, index) => (
                  <div
                    key={layer.id}
                    className="rounded-xl border border-border bg-muted/25 p-4 transition-colors hover:bg-muted/35"
                  >
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-black">Layer {index + 1}</p>
                        <p className="text-xs text-muted-foreground">
                          Frame chunking defaults are applied by the payload builder.
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="destructive"
                        size="icon-sm"
                        aria-label={`Delete layer ${index + 1}`}
                        disabled={layers.length === 1}
                        onClick={() => removeLayer(layer.id)}
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>

                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(10rem,0.8fr)_minmax(12rem,2fr)_minmax(8rem,0.7fr)]">
                      <div className="space-y-2">
                        <Label htmlFor={`layer-name-${layer.id}`}>Layer Name</Label>
                        <Input
                          id={`layer-name-${layer.id}`}
                          value={layer.name}
                          onChange={updateLayer(index, "name")}
                          placeholder="beauty"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor={`layer-command-${layer.id}`}>
                          Execution Command
                        </Label>
                        <Textarea
                          id={`layer-command-${layer.id}`}
                          value={layer.command}
                          onChange={updateLayer(index, "command")}
                          rows={2}
                          placeholder="hython render.py --frames 1-100"
                          className="font-mono"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor={`layer-range-${layer.id}`}>Frame Range</Label>
                        <Input
                          id={`layer-range-${layer.id}`}
                          value={layer.frameRange}
                          onChange={updateLayer(index, "frameRange")}
                          placeholder="1-100"
                          required
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
