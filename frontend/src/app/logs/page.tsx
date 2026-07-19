import { BrainCircuit } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LogsPage() {
  return (
    <div className="h-screen overflow-y-auto bg-background p-6 text-foreground font-mono">
      <div className="mx-auto max-w-7xl">
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <BrainCircuit className="text-primary" size={20} />
              AI Rules
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Agentic rule telemetry is reserved for the next backend integration pass.
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
