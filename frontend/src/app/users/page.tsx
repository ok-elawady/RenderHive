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
  Handshake,
  ChevronRight,
  Loader2,
  Mail,
  Pencil,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserRound,
  UsersRound,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  KeyRound,
  BadgeCheck,
  Lock,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  const renderSortIcon = (key: string) => {
    if (sortConfig?.key !== key) return <ArrowUpDown className="ml-2 size-4 opacity-50 group-hover:opacity-100 transition-opacity" />;
    if (sortConfig.direction === "asc") return <ArrowUp className="ml-2 size-4 text-primary" />;
    return <ArrowDown className="ml-2 size-4 text-primary" />;
  };

  const sortedUsers = useMemo(() => {
    if (!sortConfig) return users;

    return [...users].sort((a, b) => {
      const aValue = String(a[sortConfig.key as keyof User] || "").toLowerCase();
      const bValue = String(b[sortConfig.key as keyof User] || "").toLowerCase();

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [users, sortConfig]);

  const counts = useMemo(
    () => ({
      total: users.length,
      superusers: users.filter((entry) => entry.is_superuser).length,
      staff: users.filter((entry) => entry.is_staff && !entry.is_superuser).length,
      clients: users.filter((entry) => entry.access_level === "Client").length,
    }),
    [users],
  );

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

      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Total Users
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-3xl font-black tracking-tight text-foreground">{counts.total}</p>
                <p className="text-xs font-mono text-primary flex items-center gap-1.5">
                  <UsersRound size={14} /> Registered accounts
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Superusers
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-3xl font-black tracking-tight text-foreground">{counts.superusers}</p>
                <p className="text-xs font-mono text-destructive flex items-center gap-1.5">
                  <ShieldCheck size={14} /> Full Access
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Staff Accounts
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-3xl font-black tracking-tight text-foreground">{counts.staff}</p>
                <p className="text-xs font-mono text-info flex items-center gap-1.5">
                  <UserRound size={14} /> Elevated Rights
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Client Accounts
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-3xl font-black tracking-tight text-foreground">{counts.clients}</p>
                <p className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
                  <Handshake size={14} /> Standard Access
                </p>
              </CardContent>
            </Card>
          </section>

          <Card className="border-border overflow-hidden bg-card/80 backdrop-blur-sm p-0 mt-6">
            <CardContent className="p-0">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-[25%] pl-4">
                      <Button variant="ghost" size="sm" onClick={() => handleSort('first_name')} className="font-semibold flex items-center group -ml-3">
                        Full Name
                        {renderSortIcon('first_name')}
                      </Button>
                    </TableHead>
                    <TableHead className="w-[15%]">
                      <div className="flex justify-center w-full">
                        <Button variant="ghost" size="sm" onClick={() => handleSort('username')} className="font-semibold flex items-center group">
                          Username
                          {renderSortIcon('username')}
                        </Button>
                      </div>
                    </TableHead>
                    <TableHead className="w-[20%]">
                      <div className="flex justify-center w-full">
                        <Button variant="ghost" size="sm" onClick={() => handleSort('email')} className="font-semibold flex items-center group">
                          Email
                          {renderSortIcon('email')}
                        </Button>
                      </div>
                    </TableHead>
                    <TableHead className="w-[15%]">
                      <div className="flex justify-center w-full">
                        <Button variant="ghost" size="sm" onClick={() => handleSort('title_role')} className="font-semibold flex items-center group">
                          Title / Role
                          {renderSortIcon('title_role')}
                        </Button>
                      </div>
                    </TableHead>
                    <TableHead className="w-[15%]">
                      <div className="flex justify-center w-full">
                        <Button variant="ghost" size="sm" onClick={() => handleSort('access_level')} className="font-semibold flex items-center group">
                          Access Level
                          {renderSortIcon('access_level')}
                        </Button>
                      </div>
                    </TableHead>
                    <TableHead className="font-semibold pr-6 text-right w-[10%] align-middle">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
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
      </div>

      {/* Edit Profile / Details Sheet */}
      <Sheet open={selectedUser !== null} onOpenChange={(open) => !open && handleUserSelect(null)}>
        <SheetContent className="w-full border-border bg-card sm:max-w-md flex flex-col h-full overflow-hidden p-0">
          {selectedUser && (
            <>
              <SheetHeader className="border-b border-border p-6 shrink-0">
                <Avatar className="mb-4 size-14 shrink-0 rounded-lg shadow-sm">
                  <AvatarFallback className="rounded-lg bg-gradient-to-br from-[#d01fc7] to-primary text-xl font-bold text-white">
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
                      <AlertDialog>
                        <AlertDialogTrigger
                          render={
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
                            />
                          }
                        >
                          {deletingUserId === selectedUser.id ? (
                            <Loader2 className="animate-spin mr-2" size={15} />
                          ) : (
                            <Trash2 size={15} className="mr-2" />
                          )}
                          Delete User
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete User</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete{" "}
                              <span className="font-semibold text-foreground">
                                {selectedUser.username}
                              </span>
                              ? This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              variant="destructive"
                              onClick={() => handleDelete(selectedUser)}
                            >
                              Delete User
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
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
