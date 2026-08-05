"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Plus,
  Trash2,
  AlertCircle,
  FileText,
  Settings2,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Link2,
  Cpu,
  Fingerprint,
  Terminal,
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
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
type LayerCreatePayload = components["schemas"]["LayerCreate"];
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
  name: z.string().min(1, "Layer name is required"),
  layerType: z.enum(["RENDER", "UTIL", "POST"]),
  engine: z.string(),
  command: z.string().min(1, "Command is required"),
  frameRange: z.string().regex(/^[\d\s\-,x]+$/, "Invalid format (e.g. '1-100')"),
  chunkSize: z.coerce.number().min(1).default(1),
  minCores: z.coerce.number().min(1).default(1),
  minMemoryMb: z.coerce.number().min(512).default(4096),
  minGpus: z.coerce.number().min(0).default(0),
  maxRetries: z.coerce.number().min(0).default(3),
  dependsOnLayer: z.string().optional(),
  dependencyType: z.enum(["TASK_ON_TASK", "LAYER_ON_LAYER"]).optional(),
  executionMode: z.enum(["IMMEDIATE", "LAST", "WAIT_LAYER"]).default("IMMEDIATE"),
});

const dependencySchema = z.object({
  type: z.enum(["JOB_ON_JOB", "LAYER_ON_LAYER"]),
  parentJob: z.string().min(1, "Blocking Job ID is required"),
  parentLayer: z.string().optional(),
  depLayer: z.string().optional(),
});

const jobFormSchema = z
  .object({
    visibleName: z.string().regex(/^[a-zA-Z0-9_]+_v[0-9]+$/, "Must end with _v and version (e.g. _v1)"),
    project: z.string().min(1, "Project is required"),
    department: z.string().min(1, "Department is required"),
    user: z.string().min(1, "User is required"),
    priority: z.coerce.number().min(1).max(100),
    logDirectory: z.string().min(1, "Log directory is required"),
    maxTasksPerWorker: z.coerce.number().min(0),
    layers: z.array(layerSchema).min(1, "At least one layer is required"),
    dependencies: z.array(dependencySchema).optional(),
  })
  .superRefine((data, ctx) => {
    // Check for cyclic dependencies in layers
    const graph = new Map<string, string>();
    for (const layer of data.layers) {
      if (layer.executionMode === "WAIT_LAYER" && layer.dependsOnLayer) {
        // Find the actual name of the dependent layer. If they used "Layer 1", we just track it directly.
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

const departmentOptions = ["lighting", "fx", "comp", "td"];

function createLayerDraft(index: number) {
  return {
    id: `layer-${Date.now()}-${index}`,
    name: index === 0 ? "beauty" : `layer_${index + 1}`,
    layerType: "RENDER" as const,
    engine: "Houdini (Mantra/Karma)",
    command: getDefaultRenderCommand("Houdini (Mantra/Karma)", "1", "100"),
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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(jobFormSchema as any),
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

  // Watch for engine/frameRange changes to auto-update command
  useEffect(() => {
    // eslint-disable-next-line react-hooks/incompatible-library
    const subscription = form.watch((value, { name, type }) => {
      if (type === "change" && name?.startsWith("layers.")) {
        const parts = name.split(".");
        const index = parseInt(parts[1], 10);
        const fieldName = parts[2];

        if (fieldName === "engine" || fieldName === "frameRange") {
          const currentLayer = value.layers?.[index];
          if (!currentLayer) return;

          const rangeParts = (currentLayer.frameRange || "").split("-");
          const startFrame = rangeParts[0]?.trim() || "1";
          const endFrame = rangeParts[1]?.trim() || startFrame;

          form.setValue(
            `layers.${index}.command`,
            getDefaultRenderCommand(currentLayer.engine || "", startFrame, endFrame),
            { shouldValidate: true },
          );
        }
      }
    });
    return () => subscription.unsubscribe();
  }, [form]);

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
      user: data.user.trim() || "System",
      priority: data.priority,
      log_directory: data.logDirectory.trim(),
      max_tasks_per_worker: data.maxTasksPerWorker,
      layers: data.layers.map((layer) => ({
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
        tags: [],
        scene_path: "",
        scene_info: {},
        env: {},
      })),
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
    // If there are layer errors, jump to the first invalid layer tab automatically
    if (errors.layers && Array.isArray(errors.layers)) {
      const firstErrorIndex = errors.layers.findIndex((l) => l !== undefined);
      if (firstErrorIndex !== -1) {
        setSelectedLayerIndex(firstErrorIndex);
        toast.error("Layer Validation Error", {
          description: `Please fix the errors highlighted in Layer ${firstErrorIndex + 1}.`,
        });
        return;
      }
    }
    toast.error("Form Validation Error", { description: "Please fix the highlighted fields." });
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
                        <FormLabel>Job ID / Scene Name</FormLabel>
                        <FormControl>
                          <Input placeholder="LIGHT_v11" {...field} />
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
                        <FormLabel>Project</FormLabel>
                        <FormControl>
                          <Input placeholder="test" {...field} />
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
                        <FormLabel>Department</FormLabel>
                        <FormControl>
                          <div className="relative">
                            <select
                              {...field}
                              className="flex h-9 w-full appearance-none rounded-lg border border-transparent bg-input/50 pl-3 pr-8 py-2 text-sm outline-none transition-all hover:bg-input/80 hover:border-border/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
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
                            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="user"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>User</FormLabel>
                        <FormControl>
                          <Input placeholder="John Doe" {...field} />
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
                        <FormLabel>Log Directory</FormLabel>
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
                        <FormLabel>Priority (1-100)</FormLabel>
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
                        <FormLabel>Max Tasks/Worker</FormLabel>
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
                          Dependencies
                        </CardTitle>
                        <CardDescription>Optionally block this job until other jobs finish.</CardDescription>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-6">
                      {depFields.length === 0 ? (
                        <div className="text-center py-6 text-sm text-muted-foreground">
                          No dependencies configured. Job will be eligible to run immediately.
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {depFields.map((field, index) => {
                            const typeValue = form.watch(`dependencies.${index}.type`);
                            return (
                              <div
                                key={field.id}
                                className="relative rounded-lg border border-border p-4 bg-surface/50 space-y-4"
                              >
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
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
                                        <FormLabel>Blocking Job</FormLabel>
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
                                        <FormLabel>Blocking Layer (Optional)</FormLabel>
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
                                        <FormLabel>Block This Local Layer (Optional)</FormLabel>
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
                        <Plus size={14} className="mr-2" /> Add Dependency
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
                        Render Layers
                      </CardTitle>
                      <CardDescription>Execution groups containing specific render settings.</CardDescription>
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
                        <Plus size={14} className="mr-2" /> Add Layer
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
                            <Fingerprint size={16} className="text-primary" /> Layer Identity
                          </h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.name`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Layer Name</FormLabel>
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
                                <FormItem>
                                  <FormLabel>Layer Type</FormLabel>
                                  <FormControl>
                                    <StyledSelect {...field}>
                                      <option value="RENDER">RENDER</option>
                                      <option value="UTIL">UTIL</option>
                                      <option value="POST">POST</option>
                                    </StyledSelect>
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>

                        {/* SECTION 2: Command & Environment */}
                        <div className="pt-8 border-t border-border/50 space-y-5">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Terminal size={16} className="text-primary" /> Command & Environment
                          </h4>

                          <FormField
                            control={form.control}
                            name={`layers.${selectedLayerIndex}.engine`}
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Engine Environment</FormLabel>
                                <FormControl>
                                  <StyledSelect {...field}>
                                    <option value="Houdini (Mantra/Karma)">Houdini (Mantra/Karma)</option>
                                    <option value="Maya (Arnold/V-Ray)">Maya (Arnold/V-Ray)</option>
                                    <option value="Unreal Engine 5 (MRQ)">Unreal Engine 5 (MRQ)</option>
                                    <option value="Blender (Cycles)">Blender (Cycles)</option>
                                  </StyledSelect>
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />

                          <FormField
                            control={form.control}
                            name={`layers.${selectedLayerIndex}.command`}
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel className="flex justify-between">
                                  Execution Command
                                  <span className="font-normal text-muted-foreground/60 text-[10px]">
                                    Auto-generates
                                  </span>
                                </FormLabel>
                                <FormControl>
                                  <Textarea rows={3} className="font-mono text-[13px] bg-surface-deep" {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />

                          <FormField
                            control={form.control}
                            name={`layers.${selectedLayerIndex}.frameRange`}
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Frame Range</FormLabel>
                                <FormControl>
                                  <Input placeholder="1-100" className="font-mono" {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>

                        {/* SECTION 3: Resource Requirements */}
                        <div className="pt-8 border-t border-border/50 space-y-5">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Cpu size={16} className="text-primary" /> Resource Requirements
                          </h4>

                          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                            <FormField
                              control={form.control}
                              name={`layers.${selectedLayerIndex}.chunkSize`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Task Chunk Size</FormLabel>
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
                                <FormItem>
                                  <FormLabel>Min Cores</FormLabel>
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
                                <FormItem>
                                  <FormLabel>Min Memory (MB)</FormLabel>
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
                                <FormItem>
                                  <FormLabel>Min GPUs</FormLabel>
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
                                <FormItem>
                                  <FormLabel>Max Retries</FormLabel>
                                  <FormControl>
                                    <Input type="number" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>

                        {/* SECTION 4: Internal Dependency Block */}
                        <div className="pt-8 border-t border-border/50 space-y-5">
                          <h4 className="text-sm font-bold flex items-center gap-2 text-foreground">
                            <Settings2 size={16} className="text-primary" />
                            Layer Execution Flow
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
