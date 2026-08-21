"use client";

import { useState } from "react";
import { Check, Copy, RefreshCw, Server, ShieldAlert, ShieldCheck, Wifi, WifiOff } from "lucide-react";
import { API_BASE_URL } from "@/services/api";
import { useClusterHealth } from "@/hooks/useClusterHealth";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";

export function ClusterConnectionStatus() {
  const [copied, setCopied] = useState<boolean>(false);
  const { latencyMs, isOffline, isDegraded, isValidating, recheck } = useClusterHealth();

  const handleCopyHost = async () => {
    try {
      await navigator.clipboard.writeText(API_BASE_URL);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <Popover>
      <PopoverTrigger
        render={
          <button
            type="button"
            className="flex items-center gap-2 rounded-full border border-border/80 bg-surface/80 px-2.5 py-1 text-xs font-mono transition-all hover:bg-accent/60 hover:border-border cursor-pointer shadow-xs group"
            title="Cluster Connection Status (Click to inspect)"
            aria-label="Cluster Connection Status"
          />
        }
      >
        {isOffline ? (
          <>
            <span className="relative flex size-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-destructive opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-destructive" />
            </span>
            <span className="text-destructive font-semibold">Disconnected</span>
          </>
        ) : isDegraded ? (
          <>
            <span className="size-2 rounded-full bg-warning shadow-xs shadow-warning/50" />
            <span className="text-foreground font-medium hidden sm:inline">Cluster Online</span>
            <span className="text-warning font-bold">{latencyMs}ms</span>
          </>
        ) : (
          <>
            <span className="relative flex size-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-40" />
              <span className="relative inline-flex size-2 rounded-full bg-emerald-500 shadow-xs shadow-emerald-500/50" />
            </span>
            <span className="text-foreground font-medium hidden sm:inline">Cluster Online</span>
            <span className="text-muted-foreground group-hover:text-foreground transition-colors">{latencyMs}ms</span>
          </>
        )}
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={8}
        className="w-80 p-4 bg-surface border border-border shadow-2xl rounded-xl space-y-3 font-mono text-xs"
      >
        <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
          <div className="flex items-center gap-2">
            <Server className="size-4 text-primary" />
            <span className="font-bold text-foreground text-xs">Cluster Transport</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => void recheck()}
            disabled={isValidating}
            className="size-6 text-muted-foreground hover:text-foreground"
            title="Re-check connection"
          >
            <RefreshCw className={`size-3 ${isValidating ? "animate-spin" : ""}`} />
          </Button>
        </div>

        <div className="space-y-2 text-[11px]">
          {/* Host address */}
          <div className="flex items-center justify-between bg-surface-deep border border-input rounded-md px-2.5 py-1.5">
            <span className="text-muted-foreground">Host:</span>
            <div className="flex items-center gap-1.5 font-bold text-foreground truncate max-w-[180px]">
              <span className="truncate">{API_BASE_URL.replace(/^https?:\/\//, "")}</span>
              <button
                type="button"
                onClick={handleCopyHost}
                className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                title="Copy host URL"
              >
                {copied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
              </button>
            </div>
          </div>

          {/* Health & Status */}
          <div className="flex items-center justify-between py-1 border-b border-border/30">
            <span className="text-muted-foreground">Service Health:</span>
            <span className="flex items-center gap-1.5 font-semibold">
              {isOffline ? (
                <>
                  <ShieldAlert className="size-3 text-destructive" />
                  <span className="text-destructive">Unreachable</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="size-3 text-emerald-500" />
                  <span className="text-emerald-500">Operational</span>
                </>
              )}
            </span>
          </div>

          {/* Latency */}
          <div className="flex items-center justify-between py-1 border-b border-border/30">
            <span className="text-muted-foreground">Roundtrip Latency:</span>
            <span className="font-bold text-foreground">{isOffline ? "N/A" : `${latencyMs} ms`}</span>
          </div>

          {/* Refresh Mode */}
          <div className="flex items-center justify-between py-1">
            <span className="text-muted-foreground">Sync Strategy:</span>
            <span className="text-foreground font-medium">Live polling (7s)</span>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
