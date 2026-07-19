import { Server } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function NodesPage() {
  return (
    <div className="h-screen overflow-y-auto bg-background p-6 text-foreground font-mono">
      <div className="mx-auto max-w-7xl">
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
  );
}
