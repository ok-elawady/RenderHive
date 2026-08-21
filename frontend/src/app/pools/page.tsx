"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { PoolsTab } from "@/components/pools/PoolsTab";
import { getPools, type WorkerPool, formatApiError } from "@/services/api";

export default function WorkerPoolsPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [pools, setPools] = useState<WorkerPool[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isCreatePoolOpen, setIsCreatePoolOpen] = useState<boolean>(false);

  const canAccess = user?.isSuperuser === true || user?.isStaff === true;

  const loadPools = useCallback(async (showLoadingState = true): Promise<void> => {
    if (!canAccess) return;

    if (showLoadingState) setIsLoading(true);
    setIsRefreshing(true);
    try {
      setPools(await getPools());
    } catch (error) {
      toast.error("Unable to load worker pools", {
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
    void loadPools(pools.length === 0);
  }, [canAccess, loadPools, router, pools.length]);

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
        title="Worker Pools"
        description="Organize worker nodes into hardware tiers and department routing groups."
      >
        <Button variant="outline" onClick={() => void loadPools(false)} className="gap-2">
          <RefreshCw className={isRefreshing || isLoading ? "animate-spin" : ""} size={14} />
          Refresh
        </Button>
        <Button onClick={() => setIsCreatePoolOpen(true)} className="gap-2">
          <Plus size={14} />
          Add New Pool
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6">
        <PoolsTab
          pools={pools}
          setPools={setPools}
          isLoading={isLoading}
          isCreateOpen={isCreatePoolOpen}
          setIsCreateOpen={setIsCreatePoolOpen}
        />
      </div>
    </div>
  );
}
