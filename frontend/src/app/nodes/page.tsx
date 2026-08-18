"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { NodesTab } from "@/components/nodes/NodesTab";
import { getNodes, type WorkerNode, formatApiError } from "@/services/api";

export default function WorkerNodesPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [nodes, setNodes] = useState<WorkerNode[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const canAccess = user?.isSuperuser === true || user?.isStaff === true;

  const loadNodes = useCallback(async (showLoadingState = true): Promise<void> => {
    if (!canAccess) return;

    if (showLoadingState) setIsLoading(true);
    setIsRefreshing(true);
    try {
      setNodes(await getNodes());
    } catch (error) {
      toast.error("Unable to load worker nodes", {
        description: formatApiError(error),
      });
    } finally {
      if (showLoadingState) setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [canAccess]);

  useEffect(() => {
    if (!canAccess) {
      router.replace("/");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadNodes(nodes.length === 0);
  }, [canAccess, loadNodes, router, nodes.length]);

  if (!canAccess) {
    return (
      <div className="flex min-h-screen flex-1 items-center justify-center bg-background p-6">
        <div className="flex items-center gap-3 text-sm font-mono text-muted-foreground">
          <ShieldAlert className="text-destructive" size={20} />
          Redirecting from the restricted administration area...
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background font-sans text-foreground overflow-hidden">
      <PageHeader
        title="Worker Nodes"
        description="Monitor hardware telemetry, health status, and active task execution across the render fleet."
      >
        <Button variant="outline" onClick={() => void loadNodes(false)} className="gap-2">
          <RefreshCw className={isRefreshing || isLoading ? "animate-spin" : ""} size={14} />
          Refresh
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6">
        <NodesTab
          nodes={nodes}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
