"use client";

import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  CalendarDays,
  ChevronRight,
  Loader2,
  Mail,
  Pencil,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
  Lock,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageControlBar } from "@/components/common/PageControlBar";
import { TableSortHeader } from "@/components/common/TableSortHeader";
import {
  createUser,
  deleteUser,
  formatApiError,
  getUsers,
  updateUser,
  resetUserPassword,
  type User,
  type UserAccessLevel,
  type UserTitleRole,
} from "@/services/api";

import { CreateUserForm } from "@/components/users/CreateUserForm";
import { EditUserForm } from "@/components/users/EditUserForm";
import { ResetPasswordForm } from "@/components/users/ResetPasswordForm";
import type { CreateUserFormValues, UpdateUserFormValues, ResetPasswordFormValues } from "@/components/users/schema";

function getInitials(user: User): string {
  const initials = `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`;
  return (initials || user.username.slice(0, 2)).toUpperCase();
}

function getAccessBadgeVariant(
  accessLevel: UserAccessLevel,
): "default" | "info" | "secondary" | "destructive" {
  if (accessLevel === "Superuser") return "destructive";
  if (accessLevel === "Staff") return "info";
  return "secondary";
}

function formatDate(value: string | null): string {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function ActiveUsersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const userIdParam = searchParams.get("userId");
  const { user } = useAuth();
  
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  
  const [sheetMode, setSheetMode] = useState<"view" | "edit" | "resetPassword">("view");
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [isResettingPassword, setIsResettingPassword] = useState<boolean>(false);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [accessFilter, setAccessFilter] = useState<string>("ALL");
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);

  const selectedUser = useMemo(() => {
    if (!userIdParam || users.length === 0) return null;
    return users.find((u) => String(u.id) === userIdParam) || null;
  }, [userIdParam, users]);

  const handleUserSelect = (user: User | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (user) {
      params.set("userId", String(user.id));
    } else {
      params.delete("userId");
    }
    setSheetMode("view");
    router.replace(`?${params.toString()}`, { scroll: false });
  };

  const canAccess = user?.isSuperuser === true;

  const loadUsers = useCallback(async (showLoadingState = true): Promise<void> => {
    if (!canAccess) return;

    if (showLoadingState) setIsLoading(true);
    setIsRefreshing(true);
    try {
      setUsers(await getUsers());
    } catch (error) {
      toast.error("Unable to load users", {
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

    const timer = window.setTimeout(() => {
      void loadUsers(users.length === 0);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [canAccess, loadUsers, router, users.length]);

  const handleSort = (key: string) => {
    setSortConfig(current => {
      if (current?.key === key) {
        if (current.direction === "asc") return { key, direction: "desc" };
        return null;
      }
      return { key, direction: "asc" };
    });
  };

  const sortedUsers = useMemo(() => {
    let filtered = users;
    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (u) =>
          u.full_name.toLowerCase().includes(q) ||
          u.username.toLowerCase().includes(q) ||
          (u.email && u.email.toLowerCase().includes(q)) ||
          (u.title_role && u.title_role.toLowerCase().includes(q)),
      );
    }
    if (accessFilter && accessFilter !== "ALL") {
      filtered = filtered.filter((u) => u.access_level === accessFilter);
    }

    if (!sortConfig) return filtered;

    return [...filtered].sort((a, b) => {
      const aValue = String(a[sortConfig.key as keyof User] || "").toLowerCase();
      const bValue = String(b[sortConfig.key as keyof User] || "").toLowerCase();

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [users, sortConfig, search, accessFilter]);

  const counts = useMemo(
    () => ({
      total: users.length,
      superusers: users.filter((entry) => entry.is_superuser).length,
      staff: users.filter((entry) => entry.is_staff && !entry.is_superuser).length,
      clients: users.filter((entry) => entry.access_level === "Client").length,
    }),
    [users],
  );

  const accessChips = [
    { id: "ALL", label: "All Users", count: counts.total },
    { id: "Superuser", label: "Superusers", count: counts.superusers },
    { id: "Staff", label: "Staff", count: counts.staff },
    { id: "Client", label: "Clients", count: counts.clients },
  ];

  const handleRowKeyDown = (
    event: KeyboardEvent<HTMLTableRowElement>,
    selected: User,
  ): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleUserSelect(selected);
    }
  };

  const handleCreateSubmit = async (data: CreateUserFormValues): Promise<void> => {
    setIsCreating(true);
    
    // Split full name on the first space to satisfy backend requirements
    const nameParts = data.fullName.trim().split(" ");
    const firstName = nameParts[0];
    const lastName = nameParts.slice(1).join(" ");
    
    try {
      const createdUser = await createUser({
        first_name: firstName,
        last_name: lastName,
        username: data.username.trim(),
        email: data.email.trim(),
        title_role: data.titleRole as UserTitleRole,
        access_level: data.accessLevel as UserAccessLevel,
        password: data.password,
      });
      setUsers((current) =>
        [...current, createdUser].sort((left, right) =>
          left.username.localeCompare(right.username),
        ),
      );
      setIsCreateOpen(false);
      handleUserSelect(createdUser);
      toast.success("User provisioned", {
        description: `${createdUser.username} can now access RenderHive.`,
      });
    } catch (error) {
      toast.error("Unable to create user", {
        description: formatApiError(error),
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleEditSubmit = async (data: UpdateUserFormValues): Promise<void> => {
    if (!selectedUser) return;
    setIsUpdating(true);
    
    // Split full name on the first space
    const nameParts = data.fullName.trim().split(" ");
    const firstName = nameParts[0];
    const lastName = nameParts.slice(1).join(" ");

    try {
      const updatedUser = await updateUser(selectedUser.id as number, {
        first_name: firstName,
        last_name: lastName,
        email: data.email.trim(),
        title_role: data.titleRole as UserTitleRole,
        access_level: data.accessLevel as UserAccessLevel,
      });
      setUsers((current) =>
        current.map((entry) => (entry.id === updatedUser.id ? updatedUser : entry)),
      );
      setSheetMode("view");
      toast.success("Profile updated", {
        description: `${updatedUser.username}'s access profile is synchronized.`,
      });
    } catch (error) {
      toast.error("Unable to update user", {
        description: formatApiError(error),
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleResetPasswordSubmit = async (data: ResetPasswordFormValues): Promise<void> => {
    if (!selectedUser) return;
    setIsResettingPassword(true);
    
    try {
      await resetUserPassword(selectedUser.id as number, data);
      setSheetMode("view");
      toast.success("Password reset successful", {
        description: `A new secure password has been set for ${selectedUser.username}.`,
      });
    } catch (error) {
      toast.error("Unable to reset password", {
        description: formatApiError(error),
      });
    } finally {
      setIsResettingPassword(false);
    }
  };

  const handleDelete = async (selected: User): Promise<void> => {
    setDeletingUserId(selected.id);
    try {
      await deleteUser(selected.id);
      setUsers((current) => current.filter((entry) => entry.id !== selected.id));
      handleUserSelect(null);
      toast.success("User deleted", {
        description: `${selected.username} was permanently removed.`,
      });
    } catch (error) {
      toast.error("Unable to delete user", {
        description: formatApiError(error),
      });
    } finally {
      setDeletingUserId(null);
    }
  };

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
    <div className="flex h-screen flex-col bg-background font-sans text-foreground">
      <PageHeader
        title="User Management"
        description="Provision and manage user accounts and access levels."
      >
        <Button variant="outline" onClick={() => void loadUsers(false)} className="gap-2">
          <RefreshCw className={isLoading || isRefreshing ? "animate-spin" : ""} size={14} />
          Refresh
        </Button>
        <Button onClick={() => setIsCreateOpen(true)} className="gap-2">
          <Plus size={14} />
          Add New User
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 font-mono space-y-4">
        {/* Page-level Control Bar: Matching Jobs, Nodes, and Pools pages */}
        <PageControlBar
          chips={accessChips}
          selectedChip={accessFilter}
          onSelectChip={setAccessFilter}
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search users, username, email..."
        />

        {/* Dedicated Table Card */}
        <Card className="flex flex-col border-border p-0 gap-0 overflow-hidden bg-card">
          <CardContent className="p-0 overflow-hidden">
            <Table className="table-fixed">
              <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
                <TableRow className="hover:bg-transparent bg-muted/30">
                  <TableHead className="w-[25%] pl-6">
                    <TableSortHeader
                      label="Full Name"
                      sortKey="first_name"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="left"
                    />
                  </TableHead>
                  <TableHead className="w-[15%]">
                    <TableSortHeader
                      label="Username"
                      sortKey="username"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="w-[20%]">
                    <TableSortHeader
                      label="Email"
                      sortKey="email"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="w-[15%]">
                    <TableSortHeader
                      label="Title / Role"
                      sortKey="title_role"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="w-[15%]">
                    <TableSortHeader
                      label="Access Level"
                      sortKey="access_level"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="font-semibold pr-6 text-right w-[10%] text-xs text-muted-foreground align-middle">Actions</TableHead>
                </TableRow>
              </TableHeader>
                <TableBody className="text-xs">
                  {isLoading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                        <Loader2 className="mx-auto mb-2 animate-spin text-primary" size={22} />
                        Loading secure directory...
                      </TableCell>
                    </TableRow>
                  ) : sortedUsers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                        No active users were returned.
                      </TableCell>
                    </TableRow>
                  ) : (
                    sortedUsers.map((item) => (
                      <TableRow
                        key={item.id}
                        tabIndex={0}
                        className="group cursor-pointer hover:bg-muted/40 transition-colors focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                        onClick={() => handleUserSelect(item)}
                        onKeyDown={(event) => handleRowKeyDown(event, item)}
                        aria-label={`View ${item.full_name}`}
                      >
                        <TableCell className="pl-6 py-4 text-left">
                          <span className="font-bold text-foreground">{item.full_name}</span>
                        </TableCell>
                        <TableCell className="py-4 text-muted-foreground text-center">{item.username}</TableCell>
                        <TableCell className="py-4 text-muted-foreground text-center">{item.email || "Not provided"}</TableCell>
                        <TableCell className="py-4 text-muted-foreground font-medium text-center">{item.title_role}</TableCell>
                        <TableCell className="py-4 text-center">
                          <Badge variant={getAccessBadgeVariant(item.access_level)}>
                            {item.access_level}
                          </Badge>
                        </TableCell>
                        <TableCell className="pr-6 py-4 text-right">
                          <ChevronRight className="ml-auto text-muted-foreground group-hover:text-foreground transition-colors" size={16} />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

      {/* Edit Profile / Details Sheet */}
      <Sheet open={selectedUser !== null} onOpenChange={(open) => !open && handleUserSelect(null)}>
        <SheetContent className="w-full border-border bg-card sm:max-w-md flex flex-col h-full overflow-hidden p-0">
          {selectedUser && (
            <>
              <SheetHeader className="border-b border-border p-6 shrink-0">
                <Avatar className="mb-4 size-14 shrink-0 rounded-full shadow-sm">
                  <AvatarFallback className="rounded-full bg-gradient-to-br from-[#d01fc7] to-primary text-xl font-bold text-white">
                    {getInitials(selectedUser)}
                  </AvatarFallback>
                </Avatar>
                <SheetTitle className="text-xl font-black">
                  {selectedUser.full_name}
                </SheetTitle>
                <SheetDescription className="mt-1.5 leading-relaxed">
                  @{selectedUser.username}
                </SheetDescription>
              </SheetHeader>
              
              <div className="flex-1 overflow-y-auto p-6 flex flex-col">
                {sheetMode === "edit" ? (
                  <EditUserForm
                    user={selectedUser}
                    onSubmit={handleEditSubmit}
                    onCancel={() => setSheetMode("view")}
                    isSubmitting={isUpdating}
                  />
                ) : sheetMode === "resetPassword" ? (
                  <ResetPasswordForm
                    user={selectedUser}
                    onSubmit={handleResetPasswordSubmit}
                    onCancel={() => setSheetMode("view")}
                    isSubmitting={isResettingPassword}
                  />
                ) : (
                  <div className="space-y-5 flex flex-col flex-1">
                    {/* Access Section */}
                    <div>
                      <p className="text-xs uppercase text-muted-foreground">Access</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge variant={getAccessBadgeVariant(selectedUser.access_level)}>
                          {selectedUser.access_level}
                        </Badge>
                        <Badge variant="outline">{selectedUser.title_role}</Badge>
                      </div>
                    </div>

                    <div className="grid gap-4 border-t border-border pt-5">
                      <div className="flex items-start gap-3">
                        <Mail className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs text-muted-foreground">Email Address</p>
                          <p className="mt-1 break-all text-sm">
                            {selectedUser.email || "Not provided"}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <CalendarDays className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs text-muted-foreground">Date Joined</p>
                          <p className="mt-1 text-sm">{formatDate(selectedUser.date_joined)}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <CalendarDays className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs text-muted-foreground">Last Login</p>
                          <p className="mt-1 text-sm">{formatDate(selectedUser.last_login)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="border-t border-border pt-5">
                      <p className="text-xs uppercase text-muted-foreground">Actions</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <Button
                          variant="outline"
                          onClick={() => setSheetMode("edit")}
                        >
                          <Pencil size={15} className="mr-2" />
                          Edit Profile
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => setSheetMode("resetPassword")}
                        >
                          <Lock size={15} className="mr-2" />
                          Reset Password
                        </Button>
                      </div>
                    </div>

                    <div className="pt-6 mt-auto">
                      <ConfirmDialog
                        variant="destructive"
                        title="Delete User"
                        description={
                          <>
                            Are you sure you want to delete{" "}
                            <span className="font-semibold text-foreground">
                              {selectedUser.username}
                            </span>
                            ? This action cannot be undone.
                          </>
                        }
                        confirmText="Delete User"
                        isLoading={deletingUserId === selectedUser.id}
                        onConfirm={() => handleDelete(selectedUser)}
                        trigger={
                          <Button
                            variant="ghost"
                            className="w-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                            disabled={
                              deletingUserId === selectedUser.id ||
                              String(user?.id) === String(selectedUser.id)
                            }
                            title={
                              String(user?.id) === String(selectedUser.id)
                                ? "You cannot delete your own account"
                                : undefined
                            }
                          >
                            <Trash2 size={15} className="mr-2" />
                            Delete User
                          </Button>
                        }
                      />
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* Add New User Sheet */}
      <Sheet
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!isCreating) setIsCreateOpen(open);
        }}
      >
        <SheetContent className="w-full border-border bg-card sm:max-w-md flex flex-col h-full overflow-hidden p-0">
          <SheetHeader className="border-b border-border p-6 shrink-0">
            <SheetTitle className="text-xl font-black">
              Add New User
            </SheetTitle>
            <SheetDescription className="mt-1.5 leading-relaxed">
              Set up a new team member with access to the RenderHive platform.
            </SheetDescription>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto p-6">
            <CreateUserForm
              onSubmit={handleCreateSubmit}
              onCancel={() => setIsCreateOpen(false)}
              isSubmitting={isCreating}
            />
          </div>
        </SheetContent>
      </Sheet>

    </div>
  );
}
