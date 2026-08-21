"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  Plus,
  Trash2,
  AlertCircle,
  FileText,
  Settings2,
  ChevronDown,
  CheckCircle2,
  Link2,
  Cpu,
  Fingerprint,
  Terminal,
  Film,
} from "lucide-react";
import { toast } from "sonner";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useFieldArray, type FieldErrors } from "react-hook-form";
import * as z from "zod";

import { JobSelector, LayerSelector } from "@/components/common/Selectors";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { LayerCommandBuilder } from "@/components/jobs/LayerCommandBuilder";
import { createJob, formatApiError, getDefaultRenderCommand } from "@/services/api";
import type { components } from "@/types/schema";

type CreateJobPayload = components["schemas"]["JobCreate"] & {
  dependencies?: {
    type: "JOB_ON_JOB" | "LAYER_ON_LAYER" | "TASK_ON_TASK";
    parent_job: string;
    parent_layer?: string | null;
    dep_layer?: string | null;
  }[];
};
type LayerType = components["schemas"]["LayerTypeEnum"];

const StyledSelect = React.forwardRef<HTMLSelectElement, React.ComponentProps<"select">>(
  ({ className, ...props }, ref) => (
    <div className="relative">
      <select
        ref={ref}
        className={cn(
          "flex h-9 w-full appearance-none rounded-lg border border-transparent bg-input/50 pl-3 pr-8 py-2 text-sm outline-none transition-all hover:bg-input/80 hover:border-border/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30",
          className,
        )}
        {...props}
      />
      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
    </div>
  ),
);
StyledSelect.displayName = "StyledSelect";

const layerSchema = z.object({
  id: z.string(),
  name: z.string().trim().min(1, "Pass / Layer name is required"),
  layerType: z.enum(["RENDER", "UTIL", "POST"]),
  engine: z.string().min(1, "DCC application environment is required"),
  scenePath: z.string().trim().min(1, "Scene / Script file path is required"),
  renderer: z.string().optional(),
  renderNode: z.string().optional(),
  camera: z.string().optional(),
  outputPath: z.string().optional(),
  command: z.string().trim().min(1, "Task command template is required"),
  frameRange: z.string().trim().regex(/^[\d\s\-,x]+$/, "Frame range is required (e.g. '1-100' or '1001-1120')"),
  chunkSize: z.coerce.number().min(1, "Frames per task must be at least 1").default(1),
  minCores: z.coerce.number().min(1, "Reserved CPU cores must be at least 1").default(1),
  minMemoryMb: z.coerce.number().min(512, "Reserved RAM must be at least 512 MB").default(4096),
  minGpus: z.coerce.number().min(0).default(0),
  maxRetries: z.coerce.number().min(0).default(3),
  dependsOnLayer: z.string().optional(),
  dependencyType: z.enum(["TASK_ON_TASK", "LAYER_ON_LAYER"]).optional(),
  executionMode: z.enum(["IMMEDIATE", "LAST", "WAIT_LAYER"]).default("IMMEDIATE"),
});

const dependencySchema = z.object({
  type: z.enum(["JOB_ON_JOB", "LAYER_ON_LAYER"]),
  parentJob: z.string().min(1, "Upstream parent job is required"),
  parentLayer: z.string().optional(),
  depLayer: z.string().optional(),
});

const jobFormSchema = z
  .object({
    visibleName: z
      .string()
      .trim()
      .min(1, "Job / Shot name is required")
      .regex(/^[a-zA-Z0-9_.-]+$/, "Job name may only contain letters, numbers, underscores, hyphens, and dots"),
    project: z.string().trim().min(1, "Show / Project is required"),
    department: z.string().trim().min(1, "Department is required"),
    user: z.string().trim().min(1, "Artist / Submitter is required"),
    priority: z.coerce.number().min(1, "Priority must be between 1 and 100").max(100, "Priority must be between 1 and 100"),
    logDirectory: z.string().trim().min(1, "Farm log directory is required"),
    maxTasksPerWorker: z.coerce.number().min(0).default(0),
    layers: z.array(layerSchema).min(1, "At least one render layer is required"),
    dependencies: z.array(dependencySchema).optional(),
  })
  .superRefine((data, ctx) => {
    // Check for cyclic dependencies in layers
    const graph = new Map<string, string>();
    for (const layer of data.layers) {
      if (layer.executionMode === "WAIT_LAYER" && layer.dependsOnLayer) {
        graph.set(layer.name || `Layer ${data.layers.indexOf(layer) + 1}`, layer.dependsOnLayer);
      }
    }

    const visited = new Set<string>();
    const recStack = new Set<string>();

    function hasCycle(node: string): boolean {
      if (!visited.has(node)) {
        visited.add(node);
        recStack.add(node);

        const neighbor = graph.get(node);
        if (neighbor) {
          if (!visited.has(neighbor) && hasCycle(neighbor)) return true;
          else if (recStack.has(neighbor)) return true;
        }
      }
      recStack.delete(node);
      return false;
    }

    for (const layer of data.layers) {
      const name = layer.name || `Layer ${data.layers.indexOf(layer) + 1}`;

      if (layer.executionMode === "WAIT_LAYER" && !layer.dependsOnLayer) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Blocking layer must be selected.",
          path: ["layers", data.layers.indexOf(layer), "dependsOnLayer"],
        });
      }

      if (hasCycle(name)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Cyclic dependency detected involving layer: ${name}`,
          path: ["layers", data.layers.indexOf(layer), "dependsOnLayer"],
        });
        break; // Only report one cycle to prevent UI spam
      }
    }
  });

type JobFormValues = z.infer<typeof jobFormSchema>;

const departmentOptions = ["lighting", "fx", "comp", "td", "layout", "assets"];

function createLayerDraft(index: number) {
  return {
    id: `layer-${Date.now()}-${index}`,
    name: index === 0 ? "beauty" : `layer_${index + 1}`,
    layerType: "RENDER" as const,
    engine: "Houdini (Karma/Mantra)",
    scenePath: "",
    renderer: "Karma XPU",
    renderNode: "/stage/usdrender_rop1",
    camera: "",
    outputPath: "",
    command: "",
    frameRange: "1-100",
    chunkSize: 1,
    minCores: 1,
    minMemoryMb: 4096,
    minGpus: 0,
    maxRetries: 3,
    dependsOnLayer: "",
    dependencyType: "TASK_ON_TASK" as const,
    executionMode: "IMMEDIATE" as const,
  };
}

export default function SubmitJobPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [selectedLayerIndex, setSelectedLayerIndex] = useState<number>(0);

  const form = useForm<JobFormValues>({
    resolver: zodResolver(jobFormSchema as never) as unknown as import("react-hook-form").Resolver<JobFormValues>,
    mode: "onChange",
    defaultValues: {
      visibleName: "",
      project: "test",
      department: "lighting",
      user: "",
      priority: 50,
      logDirectory: "/tmp/render_logs",
      maxTasksPerWorker: 0,
      layers: [createLayerDraft(0)],
      dependencies: [],
    },
  });

  const { fields, append, remove } = useFieldArray({
    name: "layers",
    control: form.control,
  });

  const {
    fields: depFields,
    append: appendDep,
    remove: removeDep,
  } = useFieldArray({
    name: "dependencies",
    control: form.control,
  });

  const addLayer = () => {
    append(createLayerDraft(fields.length));
    setSelectedLayerIndex(fields.length);
  };

  const removeLayer = (index: number) => {
    if (fields.length <= 1) return;
    remove(index);
    if (selectedLayerIndex >= fields.length - 1) {
      setSelectedLayerIndex(Math.max(0, fields.length - 2));
    }
  };

  const onSubmit = async (data: JobFormValues) => {
    setIsSubmitting(true);

    const payload: CreateJobPayload = {
      visible_name: data.visibleName.trim(),
      project: data.project.trim(),
      department: data.department.trim(),
      user: data.user.trim(),
      priority: data.priority,
      log_directory: data.logDirectory.trim(),
      max_tasks_per_worker: data.maxTasksPerWorker,
      layers: data.layers.map((layer) => {
        const engineLower = (layer.engine || "").toLowerCase();
        let dcc = "generic";
        if (
          engineLower.includes("houdini") ||
          engineLower.includes("karma") ||
          engineLower.includes("mantra") ||
          engineLower.includes("husk")
        ) {
          dcc = "houdini";
        } else if (engineLower.includes("maya")) {
          dcc = "maya";
        } else if (engineLower.includes("blender") || engineLower.includes("cycles")) {
          dcc = "blender";
        } else if (engineLower.includes("nuke")) {
          dcc = "nuke";
        } else if (engineLower.includes("unreal") || engineLower.includes("mrq")) {
          dcc = "unreal";
        }

        const sceneInfo: Record<string, unknown> = {
          dcc,
          renderer: layer.renderer || "",
          render_node: layer.renderNode || "",
          camera: layer.camera || "",
          output_path: layer.outputPath || "",
        };

        if (dcc === "houdini" && engineLower.includes("husk")) {
          sceneInfo.execution = { mode: "husk" };
        }

        const tags: string[] = [];
        if (dcc && dcc !== "generic") {
          tags.push(`dcc:${dcc}`);
        }

        return {
          name: layer.name.trim(),
          layer_type: layer.layerType as LayerType,
          command: layer.command.trim(),
          frame_range: layer.frameRange.trim(),
          chunk_size: layer.chunkSize,
          min_cores: layer.minCores,
          min_memory_mb: layer.minMemoryMb,
          min_gpus: layer.minGpus,
          max_retries: layer.maxRetries,
          execution_mode: layer.executionMode,
          depends_on_layer: layer.dependsOnLayer?.trim() || null,
          dependency_type: layer.dependencyType || null,
          tags,
          scene_path: (layer.scenePath || "").trim(),
          scene_info: sceneInfo,
          env: {},
        };
      }),
      dependencies:
        data.dependencies?.map((dep) => ({
          type: "JOB_ON_JOB",
          parent_job: dep.parentJob.trim(),
          parent_layer: dep.parentLayer?.trim() || null,
          dep_layer: dep.depLayer?.trim() || null,
        })) || [],
    };

    try {
      await createJob(payload);
      toast.success("Job submitted", {
        description: `${payload.visible_name} is now in the active queue.`,
      });
      router.push("/jobs");
      router.refresh();
    } catch (error) {
      toast.error("Submission failed", {
        description: formatApiError(error),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const onInvalid = (errors: FieldErrors<JobFormValues>) => {
    // If there are top-level job setting errors
    if (errors.visibleName?.message) {
      toast.error("Job Settings Incomplete", { description: errors.visibleName.message });
      return;
    }
    if (errors.project?.message) {
      toast.error("Job Settings Incomplete", { description: errors.project.message });
      return;
    }
    if (errors.department?.message) {
      toast.error("Job Settings Incomplete", { description: errors.department.message });
      return;
    }
    if (errors.user?.message) {
      toast.error("Job Settings Incomplete", { description: errors.user.message });
      return;
    }
    if (errors.logDirectory?.message) {
      toast.error("Job Settings Incomplete", { description: errors.logDirectory.message });
      return;
    }

    // If there are layer errors, jump to the first invalid layer tab automatically
    if (errors.layers && Array.isArray(errors.layers)) {
      const firstErrorIndex = errors.layers.findIndex((l) => l !== undefined);
      if (firstErrorIndex !== -1) {
        setSelectedLayerIndex(firstErrorIndex);
        const layerErr = errors.layers[firstErrorIndex] as Record<string, { message?: string }> | undefined;
        const msg =
          layerErr?.scenePath?.message ||
          layerErr?.name?.message ||
          layerErr?.command?.message ||
          layerErr?.frameRange?.message ||
          `Please fix the errors highlighted in Layer ${firstErrorIndex + 1}.`;
        toast.error(`Layer ${firstErrorIndex + 1} Error`, {
          description: msg,
        });
        return;
      }
    }
    toast.error("Form Validation Error", { description: "Please fill in all required fields." });
  };

  const currentLayerErrors = form.formState.errors.layers?.[selectedLayerIndex];
  const isCurrentLayerValid = !currentLayerErrors;

  return (
    <div className="flex flex-col bg-background font-sans text-foreground">
      <PageHeader
        title="Submit Render Job"
        description="Configure job metadata and setup executable render layers."
        backTo="/jobs"
      />

      <div className="px-6 py-6 pb-28">
        <Form {...form}>
          <form
            id="submit-job-form"
            onSubmit={form.handleSubmit(onSubmit, onInvalid)}
            className="flex flex-col gap-6 relative"
          >
            {/* --- JOB SETTINGS (FULL WIDTH) --- */}
            <Card className="border-border">
              <CardHeader className="pb-4 border-b border-border">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText size={16} className="text-primary" />
                  Job Settings
                </CardTitle>
                <CardDescription>Global metadata applied to all layers.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5 pt-5">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  <FormField
                    control={form.control}
                    name="visibleName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-semibold">Job / Shot Name</FormLabel>
                        <FormControl>
                          <Input placeholder="sq010_sh020_lighting_v001" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="project"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-semibold">Show / Project</FormLabel>
                        <FormControl>
                          <Input placeholder="DUNE_PART_THREE" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="department"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-semibold">Department / Discipline</FormLabel>
                        <div className="relative">
                          <FormControl>
                            <select
                              {...field}
                              className="flex h-9 w-full appearance-none rounded-lg border border-transparent bg-input/50 pl-3 pr-8 py-2 text-sm outline-none transition-all hover:bg-input/80 hover:border-border/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20"
                            >
                              <option value="" disabled>
                                Select
                              </option>
                              {departmentOptions.map((dep) => (
                                <option key={dep} value={dep}>
                                  {dep}
                                </option>
                              ))}
                            </select>
                          </FormControl>
                          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="user"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-semibold">Artist / Submitter</FormLabel>
                        <FormControl>
                          <Input placeholder="jdoe" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="pt-4 border-t border-border/50 grid grid-cols-1 md:grid-cols-3 gap-6">
                  <FormField
                    control={form.control}
                    name="logDirectory"
                    render={({ field }) => (
                      <FormItem className="md:col-span-1">
                        <FormLabel className="text-xs font-semibold">Farm Log Directory</FormLabel>
                        <FormControl>
                          <Input className="font-mono text-xs" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="priority"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-semibold">Dispatch Priority (1-100)</FormLabel>
                        <FormControl>
                          <Input type="number" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="maxTasksPerWorker"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-semibold">Max Concurrent Tasks / Worker</FormLabel>
                        <FormControl>
                          <Input type="number" title="0 means unlimited" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 relative">
              <div className="lg:col-span-4">
                <div className="space-y-6 lg:sticky lg:top-21 z-10">
                  {/* Dependencies Section */}
                  <Card className="border-border">
                    <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 pb-4">
                      <div>
                        <CardTitle className="text-base flex items-center gap-2">
                          <Link2 className="size-4 text-primary" />
                          Job Graph Dependencies
                        </CardTitle>
                        <CardDescription>Block execution until upstream parent jobs or passes finish.</CardDescription>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-6">
                      {depFields.length === 0 ? (
                        <div className="text-center py-6 text-sm text-muted-foreground">
                          No upstream blockers configured. Job will dispatch immediately.
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {depFields.map((field, index) => {
                            return (
                              <div
                                key={field.id}
                                className="relative rounded-lg border border-border p-4 bg-surface/50 space-y-4"
                              >
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  aria-label="Remove dependency"
                                  className="absolute top-2 right-2 size-7 text-muted-foreground hover:text-destructive"
                                  onClick={() => removeDep(index)}
                                >
                                  <Trash2 size={14} />
                                </Button>

                                <div className="grid grid-cols-1 gap-4 mr-8">
                                  <FormField
                                    control={form.control}
                                    name={`dependencies.${index}.parentJob`}
                                    render={({ field }) => (
                                      <FormItem>
                                        <FormLabel className="text-xs font-semibold">Upstream Parent Job</FormLabel>
                                        <FormControl>
                                          <JobSelector value={field.value} onChange={field.onChange} />
                                        </FormControl>
                                        <FormMessage />
                                      </FormItem>
                                    )}
                                  />

                                  <FormField
                                    control={form.control}
                                    name={`dependencies.${index}.parentLayer`}
                                    render={({ field }) => (
                                      <FormItem>
                                        <FormLabel className="text-xs font-semibold">Upstream Parent Layer</FormLabel>
                                        <FormControl>
                                          <LayerSelector
                                            jobId={form.watch(`dependencies.${index}.parentJob`)}
                                            value={field.value}
                                            onChange={field.onChange}
                                            placeholder="Any layer..."
                                          />
                                        </FormControl>
                                        <FormMessage />
                                      </FormItem>
                                    )}
                                  />

                                  <FormField
                                    control={form.control}
                                    name={`dependencies.${index}.depLayer`}
                                    render={({ field }) => (
                                      <FormItem>
                                        <FormLabel className="text-xs font-semibold">Dependent Target Layer</FormLabel>
                                        <FormControl>
                                          <StyledSelect {...field}>
                                            <option value="">Block Entire Job</option>
                                            {form.watch("layers").map((layer, idx) => (
                                              <option key={idx} value={layer.name}>
                                                {layer.name || `Layer ${idx + 1}`}
                                              </option>
                                            ))}
                                          </StyledSelect>
                                        </FormControl>
                                        <FormMessage />
                                      </FormItem>
                                    )}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => appendDep({ type: "JOB_ON_JOB", parentJob: "", parentLayer: "", depLayer: "" })}
                        className="w-full mt-4 h-[40px] border-dashed border-border text-muted-foreground hover:text-foreground bg-transparent hover:bg-muted/50"
                      >
                        <Plus size={14} className="mr-2" /> Add Dependency Blocker
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </div>

              <div className="lg:col-span-8 flex flex-col">
                <Card className="flex flex-col border-border">
                  <CardHeader className="pb-4 border-b border-border flex flex-row items-start justify-between bg-card">
                    <div className="space-y-1.5">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Settings2 size={16} className="text-primary" />
                        Render Passes / Layers
                      </CardTitle>
                      <CardDescription>Execution passes and task dispatch parameters.</CardDescription>
                    </div>
                  </CardHeader>

                  <div className="flex flex-col sm:flex-row flex-1">
                    <div className="w-full sm:w-1/3 border-b sm:border-b-0 sm:border-r border-border bg-muted/10 flex flex-col p-3 space-y-2">
                      {fields.map((field, i) => {
                        const hasErr = !!form.formState.errors.layers?.[i];
                        const layerName = form.watch(`layers.${i}.name`);
                        return (
                          <button
                            key={field.id}
                            type="button"
                            onClick={() => setSelectedLayerIndex(i)}
                            className={`w-full group flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                              i === selectedLayerIndex
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-muted bg-transparent text-muted-foreground hover:text-foreground"
                            } ${hasErr && i !== selectedLayerIndex ? "ring-1 ring-destructive text-destructive" : ""}`}
                          >
                            <span className="truncate flex items-center gap-2">
                              {hasErr && (
                                <AlertCircle size={12} className={i !== selectedLayerIndex ? "text-destructive" : ""} />
                              )}
                              {layerName || `Layer ${i + 1}`}
                            </span>
                            {fields.length > 1 ? (
                              <div
                                role="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  removeLayer(i);
                                }}
                                className={`p-1.5 rounded-md transition-colors ${i === selectedLayerIndex ? "hover:bg-primary-foreground/20 text-primary-foreground/70 hover:text-primary-foreground" : "hover:bg-destructive/10 hover:text-destructive text-muted-foreground/50"}`}
                                aria-label="Remove layer"
                              >
                                <Trash2 size={14} />
                              </div>
                            ) : (
                              <div className="p-1.5 invisible" aria-hidden="true">
                                <Trash2 size={14} />
                              </div>
                            )}
                          </button>
                        );
                      })}

                      <Button
                        type="button"
                        variant="outline"
                        onClick={addLayer}
                        className="w-full mt-2 h-[40px] border-dashed border-border text-muted-foreground hover:text-foreground bg-transparent hover:bg-muted/50"
                      >
                        <Plus size={14} className="mr-2" /> Add Render Layer
                      </Button>
                    </div>

                    <div className="w-full sm:w-2/3 flex flex-col bg-card">
                      <div className="flex items-center justify-between px-6 py-5 border-b border-border">
                        <h3 className="text-lg font-bold">Edit Layer {selectedLayerIndex + 1}</h3>
                        {isCurrentLayerValid ? (
                          <Badge variant="success" className="gap-1 bg-success/15 text-success">
                            <CheckCircle2 size={12} /> Ready
                          </Badge>
                        ) : (
                          <Badge variant="warning" className="gap-1 bg-destructive/15 text-destructive">
                            <AlertCircle size={12} /> Invalid
                          </Badge>
                        )}
                      </div>

                      <div className="p-6 flex-1 space-y-8">
                        {/* SECTION 1: Identity */}
                        <div className="space-y-5">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Fingerprint size={16} className="text-primary" /> Pass / Layer Identity
                          </h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.name`}
                              render={({ field }) => (
                                <FormItem className="space-y-1.5">
                                  <FormLabel className="text-xs font-semibold">Pass / Layer Name</FormLabel>
                                  <FormControl>
                                    <Input placeholder="beauty" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.layerType`}
                              render={({ field }) => (
                                <FormItem className="space-y-1.5">
                                  <FormLabel className="text-xs font-semibold">Task Stage / Type</FormLabel>
                                  <FormControl>
                                    <StyledSelect {...field}>
                                      <option value="RENDER">RENDER (3D/2D Render)</option>
                                      <option value="UTIL">UTIL (Pre-process / Cache)</option>
                                      <option value="POST">POST (Comp / Review)</option>
                                    </StyledSelect>
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>

                        {/* SECTION 2: Command & Scene Setup */}
                        <div className="pt-8 border-t border-border/50 space-y-6">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Terminal size={16} className="text-primary" /> Render Setup & Execution Command
                          </h4>

                          <LayerCommandBuilder form={form} layerIndex={selectedLayerIndex} />
                        </div>

                        {/* SECTION 3: Frame Range & Sequencing */}
                        <div className="pt-8 border-t border-border/50 space-y-5">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Film size={16} className="text-primary" /> Frame Range & Sequencing
                          </h4>

                          <FormField
                            control={form.control}
                            name={`layers.${selectedLayerIndex}.frameRange`}
                            render={({ field }) => (
                              <FormItem className="space-y-1.5">
                                <FormLabel className="text-xs font-semibold">Frame Range</FormLabel>
                                <FormControl>
                                  <Input placeholder="1001-1120 or 1-100" className="font-mono text-xs bg-surface-deep" {...field} />
                                </FormControl>
                                <FormDescription className="text-[11px] text-muted-foreground leading-snug">
                                  Specify frames to dispatch (e.g. <code className="font-mono text-[10px] text-foreground/80">1-100</code>, <code className="font-mono text-[10px] text-foreground/80">1001-1120</code>, or step <code className="font-mono text-[10px] text-foreground/80">1-100x2</code>).
                                </FormDescription>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>

                        {/* SECTION 4: Resource Requirements */}
                        <div className="pt-8 border-t border-border/50 space-y-5">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Cpu size={16} className="text-primary" /> Compute & Resource Requirements
                          </h4>

                          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.chunkSize`}
                              render={({ field }) => (
                                <FormItem className="space-y-1.5">
                                  <FormLabel className="text-xs font-semibold">Frames per Task / Chunk Size</FormLabel>
                                  <FormControl>
                                    <Input type="number" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.minCores`}
                              render={({ field }) => (
                                <FormItem className="space-y-1.5">
                                  <FormLabel className="text-xs font-semibold">Reserved CPU Cores</FormLabel>
                                  <FormControl>
                                    <Input type="number" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.minMemoryMb`}
                              render={({ field }) => (
                                <FormItem className="space-y-1.5">
                                  <FormLabel className="text-xs font-semibold">Reserved RAM (MB)</FormLabel>
                                  <FormControl>
                                    <Input type="number" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.minGpus`}
                              render={({ field }) => (
                                <FormItem className="space-y-1.5">
                                  <FormLabel className="text-xs font-semibold">Required GPUs</FormLabel>
                                  <FormControl>
                                    <Input type="number" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.maxRetries`}
                              render={({ field }) => (
                                <FormItem className="space-y-1.5">
                                  <FormLabel className="text-xs font-semibold">Max Error Retries</FormLabel>
                                  <FormControl>
                                    <Input type="number" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>

                        {/* SECTION 5: Internal Dependency Block */}
                        <div className="pt-8 border-t border-border/50 space-y-5">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Settings2 size={16} className="text-primary" />
                            Dispatch Mode / Flow
                          </h4>

                          <FormField
                            control={form.control}
                            name={`layers.${selectedLayerIndex}.executionMode`}
                            render={({ field }) => (
                              <FormItem className="space-y-3">
                                <FormControl>
                                  <div className="flex flex-col space-y-2">
                                    <label className="flex items-center space-x-3 space-y-0 cursor-pointer">
                                      <input
                                        type="radio"
                                        value="IMMEDIATE"
                                        checked={field.value === "IMMEDIATE"}
                                        onChange={(e) => field.onChange(e.target.value)}
                                        className="size-4 accent-primary"
                                      />
                                      <span className="text-sm font-medium">
                                        Run Immediately{" "}
                                        <span className="text-muted-foreground font-normal">(No dependencies)</span>
                                      </span>
                                    </label>

                                    <label className="flex items-center space-x-3 space-y-0 cursor-pointer">
                                      <input
                                        type="radio"
                                        value="LAST"
                                        checked={field.value === "LAST"}
                                        onChange={(e) => {
                                          field.onChange(e.target.value);
                                          form.setValue(`layers.${selectedLayerIndex}.dependsOnLayer`, "");
                                        }}
                                        className="size-4 accent-primary"
                                      />
                                      <span className="text-sm font-medium">
                                        Run Last{" "}
                                        <span className="text-muted-foreground font-normal">
                                          (Waits for all other layers)
                                        </span>
                                      </span>
                                    </label>

                                    <label className="flex items-center space-x-3 space-y-0 cursor-pointer">
                                      <input
                                        type="radio"
                                        value="WAIT_LAYER"
                                        checked={field.value === "WAIT_LAYER"}
                                        onChange={(e) => field.onChange(e.target.value)}
                                        className="size-4 accent-primary"
                                      />
                                      <span className="text-sm font-medium">Wait for specific layer</span>
                                    </label>
                                  </div>
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />

                          {form.watch(`layers.${selectedLayerIndex}.executionMode`) === "WAIT_LAYER" && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 pl-7">
                              <FormField
                                control={form.control}
                                name={`layers.${selectedLayerIndex}.dependsOnLayer`}
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Blocking Layer</FormLabel>
                                    <FormControl>
                                      <StyledSelect {...field}>
                                        <option value="">Select layer...</option>
                                        {form.watch("layers").map((layer, idx) => {
                                          if (idx === selectedLayerIndex) return null;
                                          return (
                                            <option key={idx} value={layer.name || `Layer ${idx + 1}`}>
                                              {layer.name || `Layer ${idx + 1}`}
                                            </option>
                                          );
                                        })}
                                      </StyledSelect>
                                    </FormControl>
                                    <FormMessage />
                                  </FormItem>
                                )}
                              />

                              <FormField
                                control={form.control}
                                name={`layers.${selectedLayerIndex}.dependencyType`}
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Unblocking Trigger</FormLabel>
                                    <FormControl>
                                      <StyledSelect {...field}>
                                        <option value="TASK_ON_TASK">Task-on-Task</option>
                                        <option value="LAYER_ON_LAYER">Require All (Layer-on-Layer)</option>
                                      </StyledSelect>
                                    </FormControl>
                                    <FormMessage />
                                  </FormItem>
                                )}
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          </form>
        </Form>
      </div>

      <div className="fixed bottom-0 left-0 right-0 z-40 lg:left-64 flex items-center justify-between border-t border-border/50 bg-background/80 backdrop-blur-xl px-8 py-4">
        <div className="text-xs text-muted-foreground hidden sm:block">
          <span className="font-bold text-foreground">{fields.length}</span> layer{fields.length > 1 ? "s" : ""}{" "}
          configured
        </div>
        <div className="flex gap-4 w-full sm:w-auto justify-end">
          <Button type="button" variant="ghost" onClick={() => router.push("/jobs")}>
            Cancel
          </Button>
          <Button type="submit" form="submit-job-form" size="lg" disabled={isSubmitting} className="px-10">
            {isSubmitting ? "Submitting..." : "Submit Job to Queue"}
          </Button>
        </div>
      </div>
    </div>
  );
}
