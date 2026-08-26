"use client";

import * as React from "react";
import { useState, useEffect, useCallback } from "react";
import {
  Terminal,
  Sparkles,
  Layers,
  Camera,
  FileCode,
  HardDrive,
  Copy,
  Check,
  Code2,
  Sliders,
  HelpCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useWatch, type UseFormReturn } from "react-hook-form";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import { generateLayerCommand } from "@/services/api";

export interface LayerCommandBuilderProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
  layerIndex: number;
}

const ENGINE_OPTIONS = [
  {
    id: "Houdini (Karma/Mantra)",
    label: "Houdini (Karma / Mantra)",
    dcc: "houdini",
    defaultRenderer: "Karma XPU",
    renderers: ["Karma XPU", "Karma CPU", "Mantra", "Redshift", "V-Ray", "Arnold"],
    renderNodePlaceholder: "/stage/usdrender_rop1 or /out/karma1",
  },
  {
    id: "Houdini (Husk Standalone)",
    label: "Houdini (Husk Standalone)",
    dcc: "usd",
    defaultRenderer: "Karma XPU",
    renderers: ["Karma XPU", "Karma CPU", "Storm"],
    renderNodePlaceholder: "Optional",
  },
  {
    id: "Maya (Arnold/V-Ray)",
    label: "Maya (Arnold / V-Ray / Redshift)",
    dcc: "maya",
    defaultRenderer: "arnold",
    renderers: ["arnold", "vray", "redshift", "mayaSoftware"],
    renderNodePlaceholder: "defaultRenderGlobals",
  },
  {
    id: "Blender (Cycles)",
    label: "Blender (Cycles / Eevee)",
    dcc: "blender",
    defaultRenderer: "CYCLES",
    renderers: ["CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"],
    renderNodePlaceholder: "Optional (Scene Name)",
  },
  {
    id: "Unreal Engine 5 (MRQ)",
    label: "Unreal Engine 5 (MRQ)",
    dcc: "unreal",
    defaultRenderer: "MRQ",
    renderers: ["MRQ"],
    renderNodePlaceholder: "MoviePipelineConfig",
  },
  {
    id: "Nuke",
    label: "Nuke (CLI Render)",
    dcc: "nuke",
    defaultRenderer: "",
    renderers: [],
    renderNodePlaceholder: "Write1",
  },
  {
    id: "Custom CLI",
    label: "Custom CLI / Shell Command",
    dcc: "generic",
    defaultRenderer: "",
    renderers: [],
    renderNodePlaceholder: "",
  },
];

export function detectDccFromPath(path: string) {
  if (!path || !path.trim()) return null;
  const clean = path.trim().replace(/["']/g, "");
  const lastSegment = clean.split(/[/\\]/).pop() || "";
  const ext = lastSegment.includes(".") ? lastSegment.split(".").pop()?.toLowerCase() : "";
  if (!ext) return null;

  if (["hip", "hiplc", "hipnc"].includes(ext)) {
    return {
      engine: "Houdini (Karma/Mantra)",
      renderer: "Karma XPU",
      renderNode: "/stage/usdrender_rop1",
      ext: ext.toUpperCase(),
    };
  }
  if (["mb", "ma"].includes(ext)) {
    return {
      engine: "Maya (Arnold/V-Ray)",
      renderer: "arnold",
      renderNode: "defaultRenderGlobals",
      ext: ext.toUpperCase(),
    };
  }
  if (["blend"].includes(ext)) {
    return {
      engine: "Blender (Cycles)",
      renderer: "CYCLES",
      renderNode: "",
      ext: ext.toUpperCase(),
    };
  }
  if (["nk"].includes(ext)) {
    return {
      engine: "Nuke",
      renderer: "",
      renderNode: "Write1",
      ext: ext.toUpperCase(),
    };
  }
  if (["usd", "usda", "usdc", "usdz"].includes(ext)) {
    return {
      engine: "Houdini (Husk Standalone)",
      renderer: "Karma XPU",
      renderNode: "",
      ext: ext.toUpperCase(),
    };
  }
  return null;
}

export function LayerCommandBuilder({ form, layerIndex }: LayerCommandBuilderProps) {
  const [isRawCommandMode, setIsRawCommandMode] = useState<boolean>(false);
  const [copiedCommand, setCopiedCommand] = useState<boolean>(false);

  // Subscribe reactively to all fields of this layer
  const currentEngine =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.engine`,
    }) || "Houdini (Karma/Mantra)";

  const currentScenePath =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.scenePath`,
    }) || "";

  const currentRenderer =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.renderer`,
    }) || "";

  const currentRenderNode =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.renderNode`,
    }) || "";

  const currentCamera =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.camera`,
    }) || "";

  const currentOutputPath =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.outputPath`,
    }) || "";

  const currentFrameRange =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.frameRange`,
    }) || "1-100";

  const currentCommand =
    useWatch({
      control: form.control,
      name: `layers.${layerIndex}.command`,
    }) || "";

  // Find active engine config
  const activeEngineConfig =
    ENGINE_OPTIONS.find((e) => e.id === currentEngine) || ENGINE_OPTIONS[0];

  // Helper to re-generate command with current/overridden values
  const syncCommand = useCallback(
    (overrides?: Partial<{
      engine: string;
      renderer: string;
      scenePath: string;
      renderNode: string;
      camera: string;
      outputPath: string;
      frameRange: string;
    }>) => {
      if (isRawCommandMode) return;

      const engine = overrides?.engine ?? form.getValues(`layers.${layerIndex}.engine`) ?? currentEngine;
      const scenePath = overrides?.scenePath ?? form.getValues(`layers.${layerIndex}.scenePath`) ?? currentScenePath;
      const renderer = overrides?.renderer ?? form.getValues(`layers.${layerIndex}.renderer`) ?? currentRenderer;
      const renderNode = overrides?.renderNode ?? form.getValues(`layers.${layerIndex}.renderNode`) ?? currentRenderNode;
      const camera = overrides?.camera ?? form.getValues(`layers.${layerIndex}.camera`) ?? currentCamera;
      const outputPath = overrides?.outputPath ?? form.getValues(`layers.${layerIndex}.outputPath`) ?? currentOutputPath;
      const frameRange = overrides?.frameRange ?? form.getValues(`layers.${layerIndex}.frameRange`) ?? currentFrameRange;

      const parts = (frameRange || "").split("-");
      const startFrame = parts[0]?.trim() || "1";
      const endFrame = parts[1]?.trim() || startFrame;

      const generated = generateLayerCommand({
        engine,
        renderer: renderer || activeEngineConfig.defaultRenderer,
        scenePath,
        startFrame,
        endFrame,
        renderNode,
        camera,
        outputPath,
        useDynamicTokens: true,
      });

      form.setValue(`layers.${layerIndex}.command`, generated, { shouldValidate: true, shouldDirty: true });
    },
    [
      isRawCommandMode,
      currentEngine,
      currentScenePath,
      currentRenderer,
      currentRenderNode,
      currentCamera,
      currentOutputPath,
      currentFrameRange,
      activeEngineConfig.defaultRenderer,
      form,
      layerIndex,
    ],
  );

  // Initial and reactive sync
  useEffect(() => {
    syncCommand();
  }, [syncCommand]);

  // Synchronous handler for Scene Path changes (typing or pasting)
  const handleScenePathChange = (newPath: string) => {
    form.setValue(`layers.${layerIndex}.scenePath`, newPath, { shouldValidate: true, shouldDirty: true });

    const detected = detectDccFromPath(newPath);
    let targetEngine = currentEngine;
    let targetRenderer = currentRenderer;
    let targetRenderNode = currentRenderNode;

    if (detected) {
      targetEngine = detected.engine;
      targetRenderer = detected.renderer;
      targetRenderNode = detected.renderNode;

      form.setValue(`layers.${layerIndex}.engine`, detected.engine, { shouldValidate: true, shouldDirty: true });
      form.setValue(`layers.${layerIndex}.renderer`, detected.renderer, { shouldValidate: true, shouldDirty: true });
      form.setValue(`layers.${layerIndex}.renderNode`, detected.renderNode, { shouldValidate: true, shouldDirty: true });
    }

    syncCommand({
      scenePath: newPath,
      engine: targetEngine,
      renderer: targetRenderer,
      renderNode: targetRenderNode,
    });
  };

  const handleEngineChange = (newEngine: string) => {
    const engineOpt = ENGINE_OPTIONS.find((opt) => opt.id === newEngine) || ENGINE_OPTIONS[0];
    const newRenderer = engineOpt.defaultRenderer;
    let newRenderNode = form.getValues(`layers.${layerIndex}.renderNode`) || "";

    if (newEngine.includes("Houdini") && !newEngine.includes("Husk")) {
      newRenderNode = "/stage/usdrender_rop1";
    } else if (newEngine.includes("Maya")) {
      newRenderNode = "defaultRenderGlobals";
    } else if (newEngine.includes("Nuke")) {
      newRenderNode = "Write1";
    } else if (newEngine.includes("Husk") || newEngine.includes("Blender")) {
      newRenderNode = "";
    }

    form.setValue(`layers.${layerIndex}.engine`, newEngine, { shouldValidate: true, shouldDirty: true });
    form.setValue(`layers.${layerIndex}.renderer`, newRenderer, { shouldValidate: true, shouldDirty: true });
    form.setValue(`layers.${layerIndex}.renderNode`, newRenderNode, { shouldValidate: true, shouldDirty: true });

    syncCommand({
      engine: newEngine,
      renderer: newRenderer,
      renderNode: newRenderNode,
    });
  };

  const handleRendererChange = (newRenderer: string) => {
    form.setValue(`layers.${layerIndex}.renderer`, newRenderer, { shouldValidate: true, shouldDirty: true });
    syncCommand({ renderer: newRenderer });
  };

  const handleRenderNodeChange = (newNode: string) => {
    form.setValue(`layers.${layerIndex}.renderNode`, newNode, { shouldValidate: true, shouldDirty: true });
    syncCommand({ renderNode: newNode });
  };

  const handleCameraChange = (newCamera: string) => {
    form.setValue(`layers.${layerIndex}.camera`, newCamera, { shouldValidate: true, shouldDirty: true });
    syncCommand({ camera: newCamera });
  };

  const handleOutputPathChange = (newOutput: string) => {
    form.setValue(`layers.${layerIndex}.outputPath`, newOutput, { shouldValidate: true, shouldDirty: true });
    syncCommand({ outputPath: newOutput });
  };

  const handleCopyCommand = () => {
    if (currentCommand) {
      navigator.clipboard.writeText(currentCommand);
      setCopiedCommand(true);
      toast.info("Command copied to clipboard");
      setTimeout(() => setCopiedCommand(false), 2000);
    }
  };

  const detectedInfo = detectDccFromPath(currentScenePath);
  const detectedExt = detectedInfo?.ext || (currentScenePath.trim().includes(".") ? currentScenePath.trim().split(".").pop()?.toUpperCase() : "");

  return (
    <div className="space-y-6">
      {/* ── SECTION: Scene File Input ──────────────────────────────────────── */}
      <div className="space-y-1.5">
        <div className="flex flex-col gap-0.5">
          <FormLabel className="text-xs font-bold flex items-center gap-1.5 text-foreground">
            <HardDrive size={14} className="text-primary" />
            <span>Scene / Script File Path</span>
          </FormLabel>
          <span className="text-xs font-normal text-muted-foreground leading-snug">
            Network UNC or shared drive path (e.g. <code className="font-mono text-[11px] text-foreground/80">P:/...</code> or <code className="font-mono text-[11px] text-foreground/80">\\nas\...</code>)
          </span>
        </div>

        <FormField
          control={form.control}
          name={`layers.${layerIndex}.scenePath`}
          render={({ field }) => (
            <FormItem className="w-full space-y-1.5">
              <div className="relative">
                <FormControl>
                  <Input
                    placeholder="e.g. P:/shows/dune/shots/sq01/sh020/lighting/sh020_light_v004.hip"
                    className="font-mono text-xs bg-surface-deep pr-16 h-10 border-border/80 focus-visible:border-primary"
                    value={field.value || ""}
                    onChange={(e) => {
                      field.onChange(e);
                      handleScenePathChange(e.target.value);
                    }}
                    onPaste={(e) => {
                      const pasted = e.clipboardData.getData("text");
                      if (pasted) {
                        handleScenePathChange(pasted);
                      }
                    }}
                  />
                </FormControl>
                {field.value && detectedExt && (
                  <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none">
                    <Badge variant="outline" className="text-[11px] uppercase font-mono py-0 px-1.5 border-primary/40 bg-primary/10 text-primary">
                      .{detectedExt}
                    </Badge>
                  </div>
                )}
              </div>
              <FormDescription className="text-xs text-muted-foreground leading-snug">
                Pasting or typing the scene path automatically detects the DCC engine and generates the worker command.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      {/* ── SECTION: Engine & Renderer Setup ──────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {/* Engine Selection */}
        <FormField
          control={form.control}
          name={`layers.${layerIndex}.engine`}
          render={({ field }) => (
            <FormItem className="space-y-1.5">
              <FormLabel className="text-xs font-semibold flex items-center gap-1">
                <Sparkles size={13} className="text-primary" />
                <span>DCC Application / Environment</span>
              </FormLabel>
              <FormControl>
                <select
                  {...field}
                  value={field.value || currentEngine}
                  onChange={(e) => {
                    field.onChange(e);
                    handleEngineChange(e.target.value);
                  }}
                  className="flex h-9 w-full appearance-none rounded-lg border border-border/60 bg-input/50 px-3 py-2 text-xs outline-none transition-all hover:bg-input/80 hover:border-border focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                >
                  {ENGINE_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Renderer Selection */}
        {activeEngineConfig.renderers.length > 0 && (
          <FormField
            control={form.control}
            name={`layers.${layerIndex}.renderer`}
            render={({ field }) => {
              const effectiveRenderer = activeEngineConfig.renderers.includes(field.value)
                ? field.value
                : activeEngineConfig.defaultRenderer;

              return (
                <FormItem className="space-y-1.5">
                  <FormLabel className="text-xs font-semibold flex items-center gap-1">
                    <Sliders size={13} className="text-primary" />
                    <span>Render Engine / Delegate</span>
                  </FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      value={effectiveRenderer}
                      onChange={(e) => {
                        field.onChange(e);
                        handleRendererChange(e.target.value);
                      }}
                      className="flex h-9 w-full appearance-none rounded-lg border border-border/60 bg-input/50 px-3 py-2 text-xs outline-none transition-all hover:bg-input/80 hover:border-border focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                    >
                      {activeEngineConfig.renderers.map((rnd) => (
                        <option key={rnd} value={rnd}>
                          {rnd}
                        </option>
                      ))}
                    </select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              );
            }}
          />
        )}
      </div>

      {/* ── SECTION: Render Node (ROP) ────────────────────────────────────── */}
      {activeEngineConfig.renderNodePlaceholder && (
        <div className="pt-1">
          <FormField
            control={form.control}
            name={`layers.${layerIndex}.renderNode`}
            render={({ field }) => (
              <FormItem className="space-y-1.5">
                <FormLabel className="text-xs font-semibold flex items-center gap-1">
                  <Layers size={13} className="text-primary" />
                  <span>Render Node / ROP Target</span>
                </FormLabel>
                <FormControl>
                  <Input
                    placeholder={activeEngineConfig.renderNodePlaceholder}
                    className="font-mono text-xs bg-surface-deep"
                    value={field.value || ""}
                    onChange={(e) => {
                      field.onChange(e);
                      handleRenderNodeChange(e.target.value);
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      )}

      {/* ── SECTION: 2 Optional Fields on their own dedicated row ─────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {/* Camera Override */}
        <FormField
          control={form.control}
          name={`layers.${layerIndex}.camera`}
          render={({ field }) => (
            <FormItem className="space-y-1.5">
              <FormLabel className="text-xs font-semibold flex items-center gap-1">
                <Camera size={13} className="text-primary" />
                <span>Camera Override</span>
              </FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g. shotCam or /stage/cameras/cam1"
                  className="font-mono text-xs bg-surface-deep"
                  value={field.value || ""}
                  onChange={(e) => {
                    field.onChange(e);
                    handleCameraChange(e.target.value);
                  }}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Output Directory Template */}
        <FormField
          control={form.control}
          name={`layers.${layerIndex}.outputPath`}
          render={({ field }) => (
            <FormItem className="space-y-1.5">
              <FormLabel className="text-xs font-semibold flex items-center gap-1">
                <FileCode size={13} className="text-primary" />
                <span>Output File Pattern / AOV Path</span>
              </FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g. P:/shows/dune/renders/beauty/sh020_beauty.<F4>.exr"
                  className="font-mono text-xs bg-surface-deep"
                  value={field.value || ""}
                  onChange={(e) => {
                    field.onChange(e);
                    handleOutputPathChange(e.target.value);
                  }}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      {/* ── SECTION: Command Preview & Mode Toggle ─────────────────────────── */}
      <div className="pt-4 border-t border-border/50 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <FormLabel className="text-xs font-bold flex items-center gap-1 text-foreground">
            <Terminal size={14} className="text-primary" />
            <span>Task Command Template</span>
          </FormLabel>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsRawCommandMode(!isRawCommandMode)}
              className="h-7 text-xs gap-1 px-2 text-muted-foreground hover:text-foreground"
            >
              <Code2 size={12} />
              {isRawCommandMode ? "Switch to Visual Builder" : "Edit Raw CLI"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleCopyCommand}
              className="h-7 text-xs gap-1 px-2 text-muted-foreground hover:text-foreground"
            >
              {copiedCommand ? (
                <>
                  <Check size={12} className="text-success" /> Copied
                </>
              ) : (
                <>
                  <Copy size={12} /> Copy
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Command Textarea / Live Preview Box */}
        <FormField
          control={form.control}
          name={`layers.${layerIndex}.command`}
          render={({ field }) => (
            <FormItem className="space-y-1.5">
              <FormControl>
                <Textarea
                  rows={3}
                  readOnly={!isRawCommandMode}
                  className={cn(
                    "font-mono text-xs leading-relaxed transition-all",
                    isRawCommandMode
                      ? "bg-surface-deep border-primary/50 text-foreground ring-1 ring-primary/20"
                      : "bg-surface-deep/80 border-border text-primary/95 cursor-default select-all",
                  )}
                  {...field}
                />
              </FormControl>
              <FormDescription className="text-xs flex items-center gap-1.5 text-muted-foreground/80 mt-1.5">
                <HelpCircle size={12} className="shrink-0 text-primary" />
                <span>
                  Worker Adapters dynamically resolve tokens like{" "}
                  <code className="text-primary font-mono text-[11px] bg-muted/60 px-1 py-0.5 rounded">
                    &#123;SCENE_PATH&#125;
                  </code>{" "}
                  and{" "}
                  <code className="text-primary font-mono text-[11px] bg-muted/60 px-1 py-0.5 rounded">
                    &#123;FRAME&#125;
                  </code>{" "}
                  at dispatch time.
                </span>
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    </div>
  );
}
