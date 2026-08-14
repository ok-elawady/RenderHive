"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  ChevronRight,
  LayoutDashboard,
  ListOrdered,
  LogOut,
  Server,
  Settings,
  UsersRound,
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

  const isWorkersActive = pathname.startsWith("/nodes") || pathname.startsWith("/pools");

  const displayName = user?.displayName ?? "RenderHive User";
  const role = user?.role ?? "Authenticated";
  const initials = user?.initials ?? "RH";

  return (
    <Sidebar className="border-r-0">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              render={<Link href="/" className="cursor-pointer" />}
            >
              <div className="relative flex aspect-square size-10 items-center justify-center shrink-0 mr-1">
                <Image
                  src="/Logo2.png"
                  alt="RenderHive Logo"
                  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                  loading="eager"
                  fill
                  className="object-contain"
                />
              </div>
              <div className="flex flex-col gap-0.5 leading-none font-mono">
                <span className="font-black tracking-wider bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
                  Render<span className="text-primary">Hive</span>
                </span>
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                  RENDER MANAGEMENT
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

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

            {/* Job Queue */}
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={pathname.startsWith("/jobs")}
                render={<Link href="/jobs" />}
                tooltip="Job Queue"
              >
                <ListOrdered size={18} />
                <span>Job Queue</span>
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

            {/* AI Scheduler */}
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={pathname.startsWith("/ai")}
                render={<Link href="/ai" />}
                tooltip="AI Scheduler"
              >
                <Bot size={18} />
                <span>AI Scheduler</span>
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
            <SidebarMenuButton
              size="lg"
              render={<Link href="/settings" className="cursor-pointer" />}
              tooltip="Account Settings"
            >
              <Avatar className="size-8 rounded-full">
                <AvatarFallback className="rounded-full bg-gradient-to-br from-[#d01fc7] to-primary text-xs font-bold text-white">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="font-semibold text-foreground text-sm">{displayName}</span>
                <span className="text-xs text-primary font-mono">{role}</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={logout}>
              <LogOut size={16} />
              <span>Sign Out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
