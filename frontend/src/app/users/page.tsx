"use client";

import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  BadgeCheck,
  CalendarDays,
  Eye,
  EyeOff,
  Handshake,
  ChevronRight,
  Loader2,
  Lock,
  Mail,
  Pencil,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserRound,
  UsersRound,
  WandSparkles,
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  USER_ACCESS_LEVELS,
  USER_TITLE_ROLES,
  type User,
  type CreateUserPayload,
  type UpdateUserPayload,
  type UserAccessLevel,
  type UserTitleRole,
} from "@/services/api";

interface NewUserFormState {
  firstName: string;
  lastName: string;
  username: string;
  email: string;
  titleRole: UserTitleRole;
  accessLevel: UserAccessLevel;
  password: string;
}

interface EditUserFormState {
  firstName: string;
  lastName: string;
  email: string;
  titleRole: UserTitleRole;
  accessLevel: UserAccessLevel;
}

const initialFormState: NewUserFormState = {
  firstName: "",
  lastName: "",
  username: "",
  email: "",
  titleRole: "Animator",
  accessLevel: "Client",
  password: "",
};

function getEditFormState(user: User): EditUserFormState {
  return {
    firstName: user.first_name || "",
    lastName: user.last_name || "",
    email: user.email || "",
    titleRole: USER_TITLE_ROLES.includes(user.title_role as UserTitleRole)
      ? (user.title_role as UserTitleRole)
      : "Render User",
    accessLevel: user.access_level || "Client",
  };
}

function getInitials(user: User): string {
  const initials = `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`;
  return (initials || user.username.slice(0, 2)).toUpperCase();
}

function getAccessBadgeVariant(
  accessLevel: UserAccessLevel,
): "default" | "info" | "secondary" {
  if (accessLevel === "Superuser") return "default";
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

function generateSecurePassword(): string {
  const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+";
  let pwd = "";
  for (let i = 0; i < 16; i++) {
    pwd += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return pwd;
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
  const [isEditingSheet, setIsEditingSheet] = useState<boolean>(false);
  const [editForm, setEditForm] = useState<EditUserFormState | null>(null);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);

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
    setIsEditingSheet(false);
    router.replace(`?${params.toString()}`, { scroll: false });
  };
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [form, setForm] = useState<NewUserFormState>(initialFormState);

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
      void loadUsers();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [canAccess, loadUsers, router]);

  const counts = useMemo(
    () => ({
      total: users.length,
      superusers: users.filter((entry) => entry.is_superuser).length,
      staff: users.filter((entry) => entry.is_staff && !entry.is_superuser).length,
      clients: users.filter((entry) => entry.access_level === "Client").length,
    }),
    [users],
  );

  const updateField =
    (
      field: keyof Pick<
        NewUserFormState,
        "firstName" | "lastName" | "username" | "email" | "password"
      >,
    ) =>
    (event: ChangeEvent<HTMLInputElement>): void => {
      setForm((current) => ({ ...current, [field]: event.target.value }));
    };

  const handleRowKeyDown = (
    event: KeyboardEvent<HTMLTableRowElement>,
    selected: User,
  ): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleUserSelect(selected);
    }
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    const payload: CreateUserPayload = {
      first_name: form.firstName.trim(),
      last_name: form.lastName.trim(),
      username: form.username.trim(),
      email: form.email.trim(),
      title_role: form.titleRole,
      access_level: form.accessLevel,
      password: form.password,
    };

    if (
      !payload.first_name ||
      !payload.last_name ||
      !payload.username ||
      !payload.email ||
      !payload.password
    ) {
      toast.error("Complete all required fields");
      return;
    }

    setIsCreating(true);
    try {
      const createdUser = await createUser(payload);
      setUsers((current) =>
        [...current, createdUser].sort((left, right) =>
          left.username.localeCompare(right.username),
        ),
      );
      setForm(initialFormState);
      setShowPassword(false);
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

  const toggleEditMode = (): void => {
    if (!selectedUser) return;
    setEditForm(getEditFormState(selectedUser));
    setIsEditingSheet(true);
  };

  const handleEdit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (!selectedUser || !editForm) return;

    const payload: UpdateUserPayload = {
      first_name: editForm.firstName.trim(),
      last_name: editForm.lastName.trim(),
      email: editForm.email.trim(),
      title_role: editForm.titleRole,
      access_level: editForm.accessLevel,
    };

    setIsUpdating(true);
    try {
      const updatedUser = await updateUser(selectedUser.id, payload);
      setUsers((current) =>
        current.map((entry) => (entry.id === updatedUser.id ? updatedUser : entry)),
      );
      setIsEditingSheet(false);
      setEditForm(null);
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

  const handleDelete = async (selected: User): Promise<void> => {
    setDeletingUserId(selected.id);
    try {
      await deleteUser(selected.id);
      setUsers((current) => current.filter((entry) => entry.id !== selected.id));
      setSelectedUser(null);
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
              <CardContent className="space-y-1">
                <p className="text-3xl font-bold tracking-tight text-foreground">{counts.total}</p>
                <p className="text-xs font-mono text-primary flex items-center gap-1">
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
              <CardContent className="space-y-1">
                <p className="text-3xl font-bold tracking-tight text-foreground">{counts.superusers}</p>
                <p className="text-xs font-mono text-destructive flex items-center gap-1">
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
              <CardContent className="space-y-1">
                <p className="text-3xl font-bold tracking-tight text-foreground">{counts.staff}</p>
                <p className="text-xs font-mono text-info flex items-center gap-1">
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
              <CardContent className="space-y-1">
                <p className="text-3xl font-bold tracking-tight text-foreground">{counts.clients}</p>
                <p className="text-xs font-mono text-muted-foreground flex items-center gap-1">
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
                  <TableHead className="pl-6 font-semibold w-[25%]">Full Name</TableHead>
                  <TableHead className="font-semibold w-[15%]">Username</TableHead>
                  <TableHead className="font-semibold w-[20%]">Email</TableHead>
                  <TableHead className="font-semibold w-[15%]">Title / Role</TableHead>
                  <TableHead className="font-semibold text-right w-[15%]">Access Level</TableHead>
                  <TableHead className="font-semibold pr-6 text-right w-[10%]">Actions</TableHead>
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
                ) : users.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                      No active users were returned.
                    </TableCell>
                  </TableRow>
                ) : (
                  users.map((entry) => (
                    <TableRow
                      key={entry.id}
                      tabIndex={0}
                      className="group cursor-pointer hover:bg-muted/40 transition-colors focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                      onClick={() => handleUserSelect(entry)}
                      onKeyDown={(event) => handleRowKeyDown(event, entry)}
                      aria-label={`View ${entry.full_name}`}
                    >
                      <TableCell className="pl-6 py-4">
                        <span className="font-bold text-foreground">{entry.full_name}</span>
                      </TableCell>
                      <TableCell className="py-4 text-muted-foreground">{entry.username}</TableCell>
                      <TableCell className="py-4 text-muted-foreground">{entry.email || "Not provided"}</TableCell>
                      <TableCell className="py-4 text-muted-foreground font-medium">{entry.title_role}</TableCell>
                      <TableCell className="py-4 text-right">
                        <Badge variant={getAccessBadgeVariant(entry.access_level)}>
                          {entry.access_level}
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
              
              <div className="flex-1 overflow-y-auto p-6">
                {isEditingSheet && editForm ? (
                  <form className="space-y-5" onSubmit={(event) => void handleEdit(event)}>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="edit-first-name">First Name</Label>
                        <Input
                          id="edit-first-name"
                          value={editForm.firstName}
                          onChange={(event) =>
                            setEditForm((current) =>
                              current ? { ...current, firstName: event.target.value } : current,
                            )
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="edit-last-name">Last Name</Label>
                        <Input
                          id="edit-last-name"
                          value={editForm.lastName}
                          onChange={(event) =>
                            setEditForm((current) =>
                              current ? { ...current, lastName: event.target.value } : current,
                            )
                          }
                        />
                      </div>
                      <div className="space-y-2 sm:col-span-2">
                        <Label htmlFor="edit-email">Email Address</Label>
                        <Input
                          id="edit-email"
                          type="email"
                          value={editForm.email}
                          onChange={(event) =>
                            setEditForm((current) =>
                              current ? { ...current, email: event.target.value } : current,
                            )
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="edit-title-role">Title / Role</Label>
                        <Select
                          value={editForm.titleRole}
                          onValueChange={(value) => {
                            if (value) {
                              setEditForm((current) =>
                                current
                                  ? { ...current, titleRole: value as UserTitleRole }
                                  : current,
                              );
                            }
                          }}
                        >
                          <SelectTrigger id="edit-title-role" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {USER_TITLE_ROLES.map((role) => (
                              <SelectItem key={role} value={role}>
                                {role}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="edit-access-level">Access Level</Label>
                        <Select
                          value={editForm.accessLevel}
                          onValueChange={(value) => {
                            if (value) {
                              setEditForm((current) =>
                                current
                                  ? { ...current, accessLevel: value as UserAccessLevel }
                                  : current,
                              );
                            }
                          }}
                        >
                          <SelectTrigger id="edit-access-level" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {USER_ACCESS_LEVELS.map((level) => (
                              <SelectItem key={level} value={level}>
                                {level}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 pt-4 border-t border-border mt-6">
                      <Button
                        type="button"
                        variant="outline"
                        disabled={isUpdating}
                        onClick={() => {
                          setIsEditingSheet(false);
                          setEditForm(null);
                        }}
                      >
                        Cancel
                      </Button>
                      <Button type="submit" disabled={isUpdating}>
                        {isUpdating ? (
                          <Loader2 className="animate-spin" size={16} />
                        ) : (
                          <Pencil size={16} />
                        )}
                        {isUpdating ? "Saving..." : "Save Changes"}
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="space-y-5">
                    <div>
                      <p className="text-xs uppercase text-muted-foreground">Access</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge variant={getAccessBadgeVariant(selectedUser.access_level)}>
                          {selectedUser.access_level}
                        </Badge>
                        <Badge variant="outline">{selectedUser.title_role}</Badge>
                      </div>
                    </div>
                    <div className="border-t border-border pt-5">
                      <p className="text-xs uppercase text-muted-foreground">Actions</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <Button
                          variant="outline"
                          onClick={() => toggleEditMode()}
                        >
                          <Pencil size={15} />
                          Edit Profile
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger
                            render={
                              <Button
                                variant="destructive"
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
                              <Loader2 className="animate-spin" size={15} />
                            ) : (
                              <Trash2 size={15} />
                            )}
                            Delete User
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Permanently delete user?</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to permanently delete this user? This
                                action removes {selectedUser.username} and cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel disabled={deletingUserId !== null}>
                                Cancel
                              </AlertDialogCancel>
                              <AlertDialogAction
                                disabled={deletingUserId !== null}
                                onClick={() => void handleDelete(selectedUser)}
                              >
                                <Trash2 size={15} />
                                Delete Permanently
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
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
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

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
            <form onSubmit={(event) => void handleCreate(event)}>
              
              {/* Identity Section */}
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
                    <UserRound size={16} />
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">Identity Information</h3>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="first-name">First Name</Label>
                    <Input
                      id="first-name"
                      value={form.firstName}
                      onChange={updateField("firstName")}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="last-name">Last Name</Label>
                    <Input
                      id="last-name"
                      value={form.lastName}
                      onChange={updateField("lastName")}
                      required
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      autoComplete="off"
                      value={form.username}
                      onChange={updateField("username")}
                      required
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="email">Email Address</Label>
                    <Input
                      id="email"
                      type="email"
                      value={form.email}
                      onChange={updateField("email")}
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="h-px w-full bg-border/50 mb-6" />

              {/* Role & Access Section */}
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
                    <BadgeCheck size={16} />
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">Role & Permissions</h3>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="title-role">Title / Role</Label>
                    <Select
                      value={form.titleRole}
                      onValueChange={(value) => {
                        if (value) {
                          setForm((current) => ({
                            ...current,
                            titleRole: value as UserTitleRole,
                          }));
                        }
                      }}
                    >
                      <SelectTrigger id="title-role" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {USER_TITLE_ROLES.map((role) => (
                          <SelectItem key={role} value={role}>
                            {role}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="access-level">Access Level</Label>
                    <Select
                      value={form.accessLevel}
                      onValueChange={(value) => {
                        if (value) {
                          setForm((current) => ({
                            ...current,
                            accessLevel: value as UserAccessLevel,
                          }));
                        }
                      }}
                    >
                      <SelectTrigger id="access-level" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {USER_ACCESS_LEVELS.map((level) => (
                          <SelectItem key={level} value={level}>
                            {level}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <div className="h-px w-full bg-border/50 mb-6" />

              {/* Security Section */}
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
                    <Lock size={16} />
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">Security Details</h3>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password">Password</Label>
                    <button
                      type="button"
                      className="text-xs text-primary hover:underline flex items-center gap-1"
                      onClick={() => {
                        setForm(f => ({ ...f, password: generateSecurePassword() }));
                        setShowPassword(true);
                      }}
                    >
                      <WandSparkles size={12} />
                      Generate
                    </button>
                  </div>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      className="pr-11"
                      value={form.password}
                      onChange={updateField("password")}
                      minLength={8}
                      required
                    />
                    <button
                      type="button"
                      className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                      onClick={() => setShowPassword((current) => !current)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Django password validators are applied before the account is created.
                  </p>
                </div>
              </div>
              
              <div className="flex justify-end gap-3 pt-6 border-t border-border mt-8">
                <Button
                  type="button"
                  variant="outline"
                  disabled={isCreating}
                  onClick={() => setIsCreateOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isCreating}>
                  {isCreating ? (
                    <Loader2 className="animate-spin" size={16} />
                  ) : (
                    <Plus size={16} />
                  )}
                  {isCreating ? "Creating..." : "Create User"}
                </Button>
              </div>
            </form>
          </div>
        </SheetContent>
      </Sheet>
      </div>
    </div>
  );
}
