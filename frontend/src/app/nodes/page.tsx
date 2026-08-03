"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";

import { NodesTab } from "@/components/nodes/NodesTab";
import { PoolsTab } from "@/components/pools/PoolsTab";
import { getPools, getNodes, type WorkerPool, type WorkerNode, formatApiError } from "@/services/api";

export default function InfrastructurePage() {
  const router = useRouter();
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState<string>("nodes");

  const [pools, setPools] = useState<WorkerPool[]>([]);
  const [isLoadingPools, setIsLoadingPools] = useState<boolean>(true);
  const [isRefreshingPools, setIsRefreshingPools] = useState<boolean>(false);
  const [isCreatePoolOpen, setIsCreatePoolOpen] = useState<boolean>(false);

  const [nodes, setNodes] = useState<WorkerNode[]>([]);
  const [isLoadingNodes, setIsLoadingNodes] = useState<boolean>(true);
  const [isRefreshingNodes, setIsRefreshingNodes] = useState<boolean>(false);

  const canAccess = user?.isSuperuser === true || user?.isStaff === true;

  const loadPools = useCallback(async (showLoadingState = true): Promise<void> => {
    if (!canAccess) return;

    if (showLoadingState) setIsLoadingPools(true);
    setIsRefreshingPools(true);
    try {
      setPools(await getPools());
    } catch (error) {
      toast.error("Unable to load worker pools", {
        description: formatApiError(error),
      });
    } finally {
      if (showLoadingState) setIsLoadingPools(false);
      setIsRefreshingPools(false);
    }
  }, [canAccess]);

  const loadNodes = useCallback(async (showLoadingState = true): Promise<void> => {
    if (!canAccess) return;

    if (showLoadingState) setIsLoadingNodes(true);
    setIsRefreshingNodes(true);
    try {
      setNodes(await getNodes());
    } catch (error) {
      toast.error("Unable to load worker nodes", {
        description: formatApiError(error),
      });
    } finally {
      if (showLoadingState) setIsLoadingNodes(false);
      setIsRefreshingNodes(false);
    }
  }, [canAccess]);

  useEffect(() => {
    if (!canAccess) {
      router.replace("/");
      return;
    }
    void loadPools(pools.length === 0);
    void loadNodes(nodes.length === 0);
  }, [canAccess, loadPools, loadNodes, router, pools.length, nodes.length]);

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

  const handleRefresh = () => {
    if (activeTab === "pools") {
      void loadPools(false);
    } else if (activeTab === "nodes") {
      void loadNodes(false);
    }
  };

  const isRefreshing = activeTab === "pools" ? isRefreshingPools : activeTab === "nodes" ? isRefreshingNodes : false;
  const isLoading = activeTab === "pools" ? isLoadingPools : activeTab === "nodes" ? isLoadingNodes : false;

  return (
    <div className="flex h-screen flex-col bg-background font-sans text-foreground overflow-hidden">
      <PageHeader 
        title="Infrastructure" 
        description="Monitor active worker nodes and manage routing pools."
      >
        <Button variant="outline" onClick={handleRefresh} className="gap-2">
          <RefreshCw className={isRefreshing || isLoading ? "animate-spin" : ""} size={14} />
          Refresh
        </Button>
        {activeTab === "pools" && (
          <Button onClick={() => setIsCreatePoolOpen(true)} className="gap-2">
            <Plus size={14} />
            Add New Pool
          </Button>
        )}
      </PageHeader>
      
      <Tabs 
        value={activeTab} 
        onValueChange={setActiveTab} 
        className="flex h-full flex-col"
        defaultValue="nodes"
      >
        <div className="px-6 pt-4">
          <TabsList>
            <TabsTrigger value="nodes" className="px-6">Worker Nodes</TabsTrigger>
            <TabsTrigger value="pools" className="px-6">Worker Pools</TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 overflow-y-auto p-6 pt-4">
          <TabsContent value="nodes" className="m-0 border-none p-0 h-full outline-none">
            <NodesTab 
              nodes={nodes}
              isLoading={isLoadingNodes}
            />
          </TabsContent>
          
          <TabsContent value="pools" className="m-0 border-none p-0 h-full outline-none">
            <PoolsTab 
              pools={pools}
              setPools={setPools}
              isLoading={isLoadingPools}
              isRefreshing={isRefreshingPools}
              isCreateOpen={isCreatePoolOpen}
              setIsCreateOpen={setIsCreatePoolOpen}
            />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
