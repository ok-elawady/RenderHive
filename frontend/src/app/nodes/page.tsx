import { Server } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/PageHeader";

export default function NodesPage() {
  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader 
        title="Node Pool" 
        description="Monitor and manage active worker nodes."
      />
      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
          <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <Server className="text-primary" size={20} />
              Node Pool
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Worker node routing will plug into the render manager once the node API is exposed.
          </CardContent>
        </Card>
        </div>
      </div>
    </div>
  );
}
