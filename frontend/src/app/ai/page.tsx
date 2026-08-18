"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  HelpCircle,
  Layers,
  RefreshCw,
  Save,
  Server,
  SlidersHorizontal,
  WifiOff,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { DispatchTracesTable } from "@/components/telemetry/DispatchTracesTable";
import { ModelManager } from "@/components/dashboard/ModelManager";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { StatusDot } from "@/components/ui/status-dot";
import { StatChip } from "@/components/ui/stat-chip";
import useSWR from "swr";
import { fetchAiHealth, type AiHealthStatus } from "@/services/api";

// ── Default system prompt (mirrors the one in services/ai_scheduler/prompts.py) ─
const DEFAULT_SYSTEM_PROMPT = `You are an AI task scheduler for a distributed rendering farm.
Your job is to act as a tie-breaker for rendering tasks that have very similar base scores.
Given a worker node's current hardware capabilities and a list of candidate tasks, evaluate how well each task fits the worker.

Consider these rules:
1. High-resolution rendering and GPU renderers (like Redshift or Karma XPU) benefit from workers with lots of VRAM and available system RAM.
2. If a worker is nearly fully utilized, lightweight tasks (like utility scripts or compositing) might be a safer choice than heavy 3D renders.
3. Tasks with more retries indicate instability — prefer them on the most capable worker to maximize the chance of success.
4. Your output must be strictly valid JSON matching this schema:
[
  {
    "task_id": "uuid-string",
    "score_delta": 0.0,
    "reason": "Brief explanation"
  }
]
Where score_delta is a float between -0.20 and +0.20 that nudges the base score.
Positive values make the task more likely to be dispatched to this worker.
Negative values make it less likely. Do not exceed ±0.20.
Output ONLY the JSON array. Do not include markdown formatting or any other text.`;

// ── Local storage key for persisting rule overrides ─────────────────────────
const RULES_STORAGE_KEY = "renderhive-ai-rules";

function loadSavedRules(): string {
  if (typeof window === "undefined") return DEFAULT_SYSTEM_PROMPT;
  return window.localStorage.getItem(RULES_STORAGE_KEY) ?? DEFAULT_SYSTEM_PROMPT;
}

export default function AiSchedulerPage() {
  const { data: health, isLoading: isHealthLoading, mutate } = useSWR<AiHealthStatus>(
    "/api/v1/health",
    fetchAiHealth,
    { refreshInterval: 8000, revalidateOnFocus: true }
  );

  const [rules, setRules] = useState<string>(loadSavedRules);
  const [savedRules, setSavedRules] = useState<string>(loadSavedRules);
  const [isRulesOpen, setIsRulesOpen] = useState(false);

  // ── Rules persistence ──────────────────────────────────────────────────────
  const handleSaveRules = () => {
    window.localStorage.setItem(RULES_STORAGE_KEY, rules);
    setSavedRules(rules);
    setIsRulesOpen(false);
    toast.success("Rules saved locally", {
      description:
        "Rules are stored in your browser. To apply them cluster-wide, restart the AI Scheduler with the updated prompt.",
    });
  };

  const handleResetRules = () => {
    setRules(DEFAULT_SYSTEM_PROMPT);
    window.localStorage.setItem(RULES_STORAGE_KEY, DEFAULT_SYSTEM_PROMPT);
    setSavedRules(DEFAULT_SYSTEM_PROMPT);
    toast.info("Rules reset to defaults");
  };

  const rulesChanged = rules !== savedRules;
  const isOnline = health?.status === "ok";
  const modelLoaded = health?.model_loaded === true;

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground overflow-hidden">
      <PageHeader
        title="AI Scheduler & Dispatches"
        description="Monitor the local LLM service and review candidate task dispatch traces."
      >
        <div className="flex items-center gap-2">
          {/* Dispatch Rules Dialog */}
          <Dialog open={isRulesOpen} onOpenChange={setIsRulesOpen}>
            <DialogTrigger render={<Button variant="outline" className="gap-2" />}>
              <SlidersHorizontal size={14} />
              <span>Dispatch Rules</span>
              {rulesChanged && (
                <Badge
                  variant="outline"
                  className="text-[10px] h-4 px-1.5 border-amber-500/40 text-amber-400 bg-amber-500/10 font-medium ml-0.5"
                >
                  Unsaved
                </Badge>
              )}
            </DialogTrigger>
            <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col p-6 font-sans">
              <DialogHeader className="border-b border-border/50 pb-4 shrink-0">
                <div className="flex items-center gap-2">
                  <BrainCircuit size={18} className="text-primary" />
                  <DialogTitle className="text-lg font-black text-foreground">
                    AI Dispatch Rules
                  </DialogTitle>
                </div>
                <DialogDescription className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  These rules form the system prompt sent to the LLM when evaluating candidate tasks for worker dispatch.
                </DialogDescription>
              </DialogHeader>

              <div className="flex-1 overflow-y-auto space-y-4 py-2">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-foreground">
                    System Prompt
                  </label>
                  <Textarea
                    value={rules}
                    onChange={(e) => setRules(e.target.value)}
                    rows={12}
                    className="font-mono text-xs bg-surface-deep border-border resize-none leading-relaxed p-3"
                    placeholder="Enter AI evaluation instructions..."
                    spellCheck={false}
                  />
                </div>

                <div className="text-[11px] text-muted-foreground leading-relaxed bg-muted/20 p-3 rounded-lg border border-border/40 space-y-1">
                  <p className="font-semibold text-foreground">Note on Cluster Execution:</p>
                  <p>
                    Saved rules are stored in your browser. To permanently apply them to the backend AI service, update{" "}
                    <code className="font-mono text-[10px] bg-muted/60 px-1 py-0.5 rounded">
                      services/ai_scheduler/prompts.py
                    </code>{" "}
                    and restart the container.
                  </p>
                </div>
              </div>

              <DialogFooter className="border-t border-border/50 pt-4 flex flex-row items-center justify-between gap-2 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResetRules}
                  disabled={rules === DEFAULT_SYSTEM_PROMPT}
                  className="text-xs"
                >
                  Reset to Defaults
                </Button>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsRulesOpen(false)}
                    className="text-xs"
                  >
                    Close
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveRules}
                    disabled={!rulesChanged}
                    className="text-xs gap-1.5"
                  >
                    <Save size={13} />
                    Save Rules
                  </Button>
                </div>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <ModelManager onModelChanged={() => void mutate()} />

          <Button
            variant="outline"
            className="gap-2"
            onClick={() => void mutate()}
          >
            <RefreshCw size={14} />
            Refresh
          </Button>
        </div>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* ── Service Status Card Matching Dashboard Standard ───────────── */}
        <Card className="bg-card border-border p-0 gap-0 overflow-hidden font-sans">
          <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between bg-muted/10">
            <CardTitle className="text-sm font-bold text-foreground flex items-center gap-2">
              <Server size={16} className="text-primary" />
              <span>Service Status</span>
            </CardTitle>

            <div className="flex items-center gap-2">
              {isHealthLoading ? (
                <Badge variant="outline" className="gap-1.5 text-muted-foreground">
                  <RefreshCw size={10} className="animate-spin" />
                  Checking...
                </Badge>
              ) : isOnline ? (
                modelLoaded ? (
                  <Badge variant="outline" className="gap-1.5 border-success/40 text-success bg-success/5 font-mono text-[10px] h-5">
                    <StatusDot online={true} />
                    Online
                  </Badge>
                ) : (
                  <Badge variant="outline" className="gap-1.5 border-amber-500/40 text-amber-500 bg-amber-500/5 font-mono text-[10px] h-5">
                    <StatusDot online={true} warning={true} />
                    Mock Mode
                  </Badge>
                )
              ) : (
                <Badge variant="outline" className="gap-1.5 border-destructive/40 text-destructive bg-destructive/5 font-mono text-[10px] h-5">
                  <WifiOff size={10} />
                  Unreachable
                </Badge>
              )}
            </div>
          </CardHeader>

          <CardContent className="p-4 space-y-4">
            {!isHealthLoading && !isOnline && (
              <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                <AlertTriangle size={16} className="text-destructive mt-0.5 shrink-0" />
                <div className="text-xs text-muted-foreground leading-relaxed">
                  <span className="font-semibold text-destructive">AI service is not reachable.</span> The farm will
                  continue to operate using deterministic scoring only. Start the service with{" "}
                  <code className="font-mono text-xs bg-muted/60 px-1.5 py-0.5 rounded">
                    uvicorn main:app --port 8001
                  </code>{" "}
                  or via{" "}
                  <code className="font-mono text-xs bg-muted/60 px-1.5 py-0.5 rounded">
                    docker compose --profile ai up
                  </code>
                  .
                </div>
              </div>
            )}

            {/* Model status */}
            <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-muted/20 p-3">
              <BrainCircuit size={18} className={modelLoaded ? "text-primary" : "text-muted-foreground"} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground">
                  {isHealthLoading ? "Checking model..." : modelLoaded ? "LLM Model Loaded" : "Running in Mock Mode"}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5 truncate">
                  {isHealthLoading
                    ? "Please wait..."
                    : modelLoaded
                      ? (health?.model_path ?? "Model path not reported")
                      : "No GGUF model found. Set LLAMA_MODEL_PATH to enable real inference."}
                </p>
              </div>
              {!isHealthLoading &&
                (modelLoaded ? (
                  <CheckCircle2 size={16} className="text-success shrink-0" />
                ) : (
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle size={16} className="text-muted-foreground/60 cursor-help shrink-0" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      Mock mode returns zero-delta scores. The dispatch pipeline still works correctly — deterministic
                      scoring is used as the sole ranking mechanism.
                    </TooltipContent>
                  </Tooltip>
                ))}
            </div>

            {/* Stats panel */}
            <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border/60 rounded-xl border border-border/60 bg-muted/10 overflow-hidden mt-2">
              <StatChip
                icon={Zap}
                label="Template"
                value={isHealthLoading ? "—" : (health?.prompt_template ?? "—")}
                tooltip="The chat template used to format prompts for this model family. Must match the loaded GGUF model."
              />
              <StatChip
                icon={Layers}
                label="Context"
                value={isHealthLoading ? "—" : health?.n_ctx ? `${health.n_ctx.toLocaleString()} tok` : "—"}
                tooltip="The context window size configured on the LLM. Larger values support more competitive tasks per request but require more VRAM."
              />
              <StatChip
                icon={Cpu}
                label="Max Tasks"
                value={isHealthLoading ? "—" : (health?.max_tasks_per_request ?? "—")}
                tooltip="Maximum number of competitive tasks sent to the AI per dispatch call. Prevents context window overflow."
              />
            </div>
          </CardContent>
        </Card>

        {/* ── Dispatch Traces Table ───────────────────────────────────────── */}
        <DispatchTracesTable />
      </div>
    </div>
  );
}
