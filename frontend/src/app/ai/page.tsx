"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  HelpCircle,
  Layers,
  RefreshCw,
  Save,
  Server,
  WifiOff,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import AgenticLogs from "@/components/dashboard/AgenticLogs";
import { ModelManager } from "@/components/dashboard/ModelManager";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AiSchedulerPage() {
  const { data: health, isLoading: isHealthLoading, mutate } = useSWR<AiHealthStatus>(
    "/api/v1/health",
    fetchAiHealth,
    { refreshInterval: 8000, revalidateOnFocus: true }
  );

  const [rules, setRules] = useState<string>(loadSavedRules);
  const [savedRules, setSavedRules] = useState<string>(loadSavedRules);
  const [isRulesExpanded, setIsRulesExpanded] = useState(false);

  // ── Rules persistence ──────────────────────────────────────────────────────
  const handleSaveRules = () => {
    window.localStorage.setItem(RULES_STORAGE_KEY, rules);
    setSavedRules(rules);
    toast.success("Rules saved locally", {
      description:
        "Rules are stored in your browser. To apply them to the running AI service, restart it with the updated prompts.py.",
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
        title="AI Scheduler"
        description="Monitor the local LLM service and manage dispatch tie-breaking rules."
      >
        <div className="flex items-center gap-2">
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

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* ── Service Status Card ─────────────────────────────────────────── */}
        <Card className="border-border bg-card/95 shadow-none">
          <CardHeader className="border-b border-border/50">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2.5 text-base font-black">
                <Server size={16} className="text-primary" />
                Service Status
              </CardTitle>

              {isHealthLoading ? (
                <Badge variant="outline" className="gap-1.5 text-muted-foreground">
                  <RefreshCw size={10} className="animate-spin" />
                  Checking...
                </Badge>
              ) : isOnline ? (
                modelLoaded ? (
                  <Badge variant="outline" className="gap-1.5 border-success/40 text-success bg-success/5">
                    <StatusDot online={true} />
                    Online
                  </Badge>
                ) : (
                  <Badge variant="outline" className="gap-1.5 border-amber-500/40 text-amber-500 bg-amber-500/5">
                    <StatusDot online={true} warning={true} />
                    Mock Mode
                  </Badge>
                )
              ) : (
                <Badge variant="outline" className="gap-1.5 border-destructive/40 text-destructive bg-destructive/5">
                  <WifiOff size={10} />
                  Unreachable
                </Badge>
              )}
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
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

        {/* ── Dispatch Log Feed ───────────────────────────────────────────── */}
        <div className="h-80">
          <AgenticLogs searchQuery="" />
        </div>

        {/* ── System Prompt / Rules Editor ───────────────────────────────── */}
        <Card className="border-border bg-card/95 shadow-none">
          <CardHeader className="border-b border-border/50">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <CardTitle className="text-base font-black flex items-center gap-2.5">
                  <BrainCircuit size={16} className="text-primary" />
                  Dispatch Rules
                </CardTitle>
                {rulesChanged && (
                  <Badge
                    variant="outline"
                    className="text-xs h-5 px-2 border-amber-500/40 text-amber-500 bg-amber-500/5 font-medium"
                  >
                    Unsaved
                  </Badge>
                )}
              </div>
              <button
                type="button"
                onClick={() => setIsRulesExpanded((v) => !v)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {isRulesExpanded ? (
                  <>
                    Collapse <ChevronUp size={13} />
                  </>
                ) : (
                  <>
                    Edit rules <ChevronDown size={13} />
                  </>
                )}
              </button>
            </div>
          </CardHeader>

          <CardContent className="space-y-3">
            <p className="text-xs text-muted-foreground leading-relaxed">
              These rules form the system prompt sent to the LLM when breaking dispatch ties. Edits are saved locally in
              your browser. To permanently apply changes, copy the updated prompt into{" "}
              <code className="font-mono text-xs bg-muted/60 px-1.5 py-0.5 rounded">
                services/ai_scheduler/prompts.py
              </code>{" "}
              and restart the service.
            </p>

            {isRulesExpanded && (
              <>
                <Textarea
                  value={rules}
                  onChange={(e) => setRules(e.target.value)}
                  rows={18}
                  className="font-mono text-xs leading-relaxed resize-y bg-surface-deep border-input"
                  spellCheck={false}
                />
                <div className="flex items-center justify-between gap-2 pt-1">
                  <button
                    type="button"
                    onClick={handleResetRules}
                    className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
                  >
                    Reset to defaults
                  </button>
                  <Button size="sm" className="gap-2" onClick={handleSaveRules} disabled={!rulesChanged}>
                    <Save size={13} />
                    Save Rules
                  </Button>
                </div>
              </>
            )}

            {!isRulesExpanded && (
              <div className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
                <p className="text-xs text-muted-foreground font-mono leading-relaxed line-clamp-3 opacity-70">
                  {savedRules}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
