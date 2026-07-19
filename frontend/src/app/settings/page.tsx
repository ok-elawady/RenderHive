import { Settings } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="h-screen overflow-y-auto bg-background p-6 text-foreground font-mono">
      <div className="mx-auto max-w-7xl">
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <Settings className="text-primary" size={20} />
              Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Pipeline preferences and access controls can land here when the settings schema is ready.
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
