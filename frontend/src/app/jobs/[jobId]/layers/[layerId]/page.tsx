"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, SkipForward } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  API_BASE_URL,
  formatApiError,
  getLayer,
  skipFrame,
  type FrameList,
  type FrameStateFilter,
  type LayerDetail,
} from "@/services/api";

type PaginatedFrameResponse = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results: FrameList[];
};

const FRAME_FETCH_LIMIT = 200;

const frameStates: Array<FrameStateFilter | "ALL"> = [
  "ALL",
  "READY",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
  "SKIPPED",
  "WAITING",
];

function isFrameListArray(value: unknown): value is FrameList[] {
  return Array.isArray(value);
}

function isPaginatedFrameResponse(value: unknown): value is PaginatedFrameResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "results" in value &&
    Array.isArray((value as PaginatedFrameResponse).results)
  );
}

function getApiHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_RENDERHIVE_AUTH_TOKEN;

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Token ${token}` } : {}),
  };
}

async function fetchLayerFramesWithLimit(
  jobId: string,
  layerId: string,
): Promise<FrameList[]> {
  const query = new URLSearchParams({
    limit: String(FRAME_FETCH_LIMIT),
    page_size: String(FRAME_FETCH_LIMIT),
  });
  let nextUrl: string | null =
    `${API_BASE_URL}/api/jobs/${jobId}/layers/${layerId}/frames/?${query.toString()}`;
  const allFrames: FrameList[] = [];

  while (nextUrl) {
    const response = await fetch(nextUrl, {
      headers: getApiHeaders(),
      cache: "no-store",
    });
    const payload: unknown = await response.json();

    if (!response.ok) {
      throw new Error(JSON.stringify(payload));
    }

    if (isPaginatedFrameResponse(payload)) {
      allFrames.push(...payload.results);
      nextUrl = payload.next ?? null;
      continue;
    }

    if (isFrameListArray(payload)) {
      allFrames.push(...payload);
    }

    nextUrl = null;
  }

  return allFrames;
}

function getFrameClasses(state: FrameList["state"]): string {
  if (state === "RUNNING") {
    return "border-warning bg-warning/20 text-warning animate-pulse";
  }
  if (state === "SUCCEEDED") {
    return "border-success bg-success/15 text-success";
  }
  if (state === "FAILED") {
    return "border-destructive bg-destructive/15 text-destructive";
  }
  if (state === "SKIPPED") {
    return "border-sky-400/50 bg-sky-500/15 text-sky-500 dark:text-sky-300";
  }
  if (state === "READY") {
    return "border-border bg-muted/50 text-foreground";
  }
  return "border-input bg-input/30 text-muted-foreground";
}

export default function LayerInspectorPage() {
  const params = useParams<{ jobId: string; layerId: string }>();
  const [layer, setLayer] = useState<LayerDetail | null>(null);
  const [frames, setFrames] = useState<FrameList[]>([]);
  const [stateFilter, setStateFilter] = useState<FrameStateFilter | "ALL">("ALL");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [skippingFrameId, setSkippingFrameId] = useState<string | null>(null);

  const visibleFrames = useMemo(
    () =>
      stateFilter === "ALL"
        ? frames
        : frames.filter((frame) => frame.state === stateFilter),
    [frames, stateFilter],
  );

  const refreshFrames = useCallback(async (): Promise<void> => {
    const frameData = await fetchLayerFramesWithLimit(params.jobId, params.layerId);
    setFrames(frameData);
  }, [params.jobId, params.layerId]);

  const loadLayer = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const [layerData, frameData] = await Promise.all([
        getLayer(params.jobId, params.layerId),
        fetchLayerFramesWithLimit(params.jobId, params.layerId),
      ]);
      setLayer(layerData);
      setFrames(frameData);
    } catch (error) {
      toast.error("Unable to load layer frames", {
        description: formatApiError(error),
      });
    } finally {
      setIsLoading(false);
    }
  }, [params.jobId, params.layerId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadLayer();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadLayer]);

  const handleSkipFrame = async (frameId: string): Promise<void> => {
    setSkippingFrameId(frameId);
    try {
      await skipFrame(frameId);
      setFrames((currentFrames) =>
        currentFrames.map((frame) =>
          frame.id === frameId ? { ...frame, state: "SKIPPED" } : frame,
        ),
      );
      toast.success("Frame skipped", {
        description: "The failed frame was moved to SKIPPED.",
      });
      void refreshFrames();
    } catch (error) {
      toast.error("Skip failed", { description: formatApiError(error) });
    } finally {
      setSkippingFrameId(null);
    }
  };

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader
        title={layer?.name ?? "Layer Inspector"}
        description={layer ? `${layer.layer_type} / ${layer.frame_range} / ${layer.command}` : "Fetching frames..."}
        backTo={`/jobs/${params.jobId}`}
      >
        <Button variant="outline" onClick={() => void loadLayer()} className="gap-2">
          <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          Refresh
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">

        <Tabs
          value={stateFilter}
          onValueChange={(value) => setStateFilter(value as FrameStateFilter | "ALL")}
        >
          <TabsList className="flex-wrap justify-start">
            {frameStates.map((state) => (
              <TabsTrigger key={state} value={state}>
                {state}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value={stateFilter}>
            <Card className="border-border">
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  Frame Grid
                  <Badge variant="outline">{frames.length} frames</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="flex h-56 items-center justify-center text-muted-foreground">
                    Loading frames...
                  </div>
                ) : (
                  <div className="grid grid-cols-8 gap-2 sm:grid-cols-10 md:grid-cols-12 lg:grid-cols-[repeat(16,minmax(0,1fr))] xl:grid-cols-[repeat(20,minmax(0,1fr))]">
                    {visibleFrames.map((frame) => (
                      <div
                        key={frame.id}
                        title={`${frame.name} / ${frame.state}`}
                        className={`group relative aspect-square overflow-hidden rounded-lg border text-[10px] font-black transition-all hover:scale-105 ${getFrameClasses(frame.state)}`}
                      >
                        <span className="absolute inset-0 flex items-center justify-center">
                          {frame.number}
                        </span>
                        {frame.state === "FAILED" && (
                          <button
                            type="button"
                            className="absolute inset-x-1 bottom-1 hidden rounded-md bg-background/95 px-1.5 py-1 text-[9px] font-black text-destructive shadow-lg ring-1 ring-destructive/30 transition-all hover:bg-destructive hover:text-destructive-foreground group-hover:block"
                            disabled={skippingFrameId === frame.id}
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              void handleSkipFrame(frame.id);
                            }}
                          >
                            {skippingFrameId === frame.id ? "..." : "SKIP"}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-6 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-2">
                    <i className="size-3 rounded bg-muted" /> READY
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <i className="size-3 rounded bg-warning/70" /> RUNNING
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <i className="size-3 rounded bg-success/70" /> SUCCEEDED
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <i className="size-3 rounded bg-destructive/70" /> FAILED
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <i className="size-3 rounded bg-sky-500/70" /> SKIPPED
                  </span>
                </div>

                <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                  <SkipForward size={14} className="mr-2 inline text-primary" />
                  Hover a failed frame and click SKIP to call{" "}
                  <code>POST /api/frames/&lbrace;id&rbrace;/skip/</code>.
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        </div>
      </div>
    </div>
  );
}
