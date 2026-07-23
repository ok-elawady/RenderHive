import { BrainCircuit } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/PageHeader";

export default function LogsPage() {
  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader 
        title="AI Rules" 
        description="Agentic rule telemetry and monitoring."
      />
      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
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
    </div>
  );
}
