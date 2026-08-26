"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  Server,
  Settings,
  UsersRound,
  User,
} from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

export default function AppSidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const { setOpen } = useSidebar();

  const isWorkersActive = pathname.startsWith("/nodes") || pathname.startsWith("/pools");

  const displayName = user?.displayName ?? "RenderHive User";
  const role = user?.role ?? "Authenticated";
  const initials = user?.initials ?? "RH";

  return (
    <Sidebar 
      collapsible="icon" 
      className="border-r-0 group/sidebar transition-all duration-150 z-50 overlay-on-hover"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <SidebarHeader className="hidden" />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Application</SidebarGroupLabel>
          <SidebarMenu>
            {/* Dashboard */}
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={pathname === "/"}
                render={<Link href="/" />}
                tooltip="Dashboard"
              >
                <LayoutDashboard size={18} />
                <span>Dashboard</span>
              </SidebarMenuButton>
            </SidebarMenuItem>



            {/* Workers Collapsible (Expanded by default) */}
            <Collapsible
              defaultOpen={true}
              className="group/collapsible"
            >
              <SidebarMenuItem>
                <CollapsibleTrigger
                  render={
                    <SidebarMenuButton tooltip="Workers">
                      <Server size={18} />
                      <span>Workers</span>
                      <ChevronRight className="ml-auto size-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90 group-data-open/collapsible:rotate-90" />
                    </SidebarMenuButton>
                  }
                />
                <CollapsibleContent>
                  <SidebarMenuSub>
                    <SidebarMenuSubItem>
                      <SidebarMenuSubButton
                        isActive={pathname.startsWith("/nodes")}
                        render={<Link href="/nodes" />}
                      >
                        <span>Nodes</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem>
                      <SidebarMenuSubButton
                        isActive={pathname.startsWith("/pools")}
                        render={<Link href="/pools" />}
                      >
                        <span>Pools</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>

            {/* Telemetry & Observability */}
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={pathname.startsWith("/telemetry")}
                render={<Link href="/telemetry" />}
                tooltip="Telemetry & Observability"
              >
                <Activity size={18} />
                <span>Telemetry</span>
              </SidebarMenuButton>
            </SidebarMenuItem>

            {/* AI Service */}
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={pathname.startsWith("/ai")}
                render={<Link href="/ai" />}
                tooltip="AI Service"
              >
                <Bot size={18} />
                <span>AI Service</span>
              </SidebarMenuButton>
            </SidebarMenuItem>

            {/* Superuser: User Management */}
            {user?.isSuperuser && (
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={pathname.startsWith("/users")}
                  render={<Link href="/users" />}
                  tooltip="User Management"
                >
                  <UsersRound size={18} />
                  <span>User Management</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}

            {/* Settings */}
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={pathname.startsWith("/settings")}
                render={<Link href="/settings" />}
                tooltip="Settings"
              >
                <Settings size={18} />
                <span>Settings</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex items-center justify-between group-data-[collapsible=icon]:justify-center p-2 rounded-md hover:bg-sidebar-accent transition-colors">
              <div className="flex items-center gap-2 overflow-hidden group-data-[collapsible=icon]:hidden">
                <div className="flex items-center justify-center size-8 rounded-full bg-muted border border-border/50 shrink-0">
                  <User className="size-5 text-muted-foreground" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none min-w-0">
                  <span className="font-semibold text-foreground text-sm truncate">{displayName}</span>
                  <span className="text-xs text-primary font-mono truncate">{role}</span>
                </div>
              </div>
              
              {/* Show only icon when collapsed */}
              <div className="hidden group-data-[collapsible=icon]:flex items-center justify-center size-8 rounded-full bg-muted border border-border/50 shrink-0">
                <User className="size-5 text-muted-foreground" />
              </div>

              <button
                onClick={logout}
                className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors rounded-md shrink-0 group-data-[collapsible=icon]:hidden"
                title="Sign Out"
              >
                <LogOut size={16} />
              </button>
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
