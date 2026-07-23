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
  CalendarDays,
  Eye,
  EyeOff,
  Handshake,
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
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/AuthProvider";
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
  createAdminUser,
  deleteAdminUser,
  formatApiError,
  getAdminUsers,
  updateAdminUser,
  USER_ACCESS_LEVELS,
  USER_TITLE_ROLES,
  type AdminUser,
  type CreateAdminUserPayload,
  type UpdateAdminUserPayload,
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

function getEditFormState(user: AdminUser): EditUserFormState {
  return {
    firstName: user.first_name,
    lastName: user.last_name,
    email: user.email,
    titleRole: USER_TITLE_ROLES.includes(user.title_role as UserTitleRole)
      ? (user.title_role as UserTitleRole)
      : "Animator",
    accessLevel: user.access_level,
  };
}

function getInitials(user: AdminUser): string {
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

export default function ActiveUsersPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [editForm, setEditForm] = useState<EditUserFormState | null>(null);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [form, setForm] = useState<NewUserFormState>(initialFormState);

  const canAccess = user?.isSuperuser === true;

  const loadUsers = useCallback(async (): Promise<void> => {
    if (!canAccess) return;

    setIsLoading(true);
    try {
      setUsers(await getAdminUsers());
    } catch (error) {
      toast.error("Unable to load users", {
        description: formatApiError(error),
      });
    } finally {
      setIsLoading(false);
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
    selected: AdminUser,
  ): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setSelectedUser(selected);
    }
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    const payload: CreateAdminUserPayload = {
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
      const createdUser = await createAdminUser(payload);
      setUsers((current) =>
        [...current, createdUser].sort((left, right) =>
          left.username.localeCompare(right.username),
        ),
      );
      setForm(initialFormState);
      setShowPassword(false);
      setIsCreateOpen(false);
      setSelectedUser(createdUser);
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

  const openEditDialog = (selected: AdminUser): void => {
    setEditForm(getEditFormState(selected));
    setEditingUser(selected);
    setSelectedUser(null);
  };

  const handleEdit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (!editingUser || !editForm) return;

    const payload: UpdateAdminUserPayload = {
      first_name: editForm.firstName.trim(),
      last_name: editForm.lastName.trim(),
      email: editForm.email.trim(),
      title_role: editForm.titleRole,
      access_level: editForm.accessLevel,
    };

    setIsUpdating(true);
    try {
      const updatedUser = await updateAdminUser(editingUser.id, payload);
      setUsers((current) =>
        current.map((entry) => (entry.id === updatedUser.id ? updatedUser : entry)),
      );
      setEditingUser(null);
      setEditForm(null);
      setSelectedUser(updatedUser);
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

  const handleDelete = async (selected: AdminUser): Promise<void> => {
    setDeletingUserId(selected.id);
    try {
      await deleteAdminUser(selected.id);
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
    <div className="h-screen overflow-y-auto bg-background p-4 text-foreground sm:p-6 font-mono">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-primary">
              Restricted Administration
            </p>
            <h1 className="mt-1 text-2xl font-black tracking-tight">Active Users</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Provision and inspect accounts with server-enforced superuser access.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void loadUsers()} disabled={isLoading}>
              <RefreshCw className={isLoading ? "animate-spin" : ""} size={15} />
              Refresh
            </Button>
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus size={16} />
              Add New User
            </Button>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
          <Card className="border-border bg-card">
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <p className="text-xs uppercase text-muted-foreground">Active accounts</p>
                <p className="mt-1 text-2xl font-black">{counts.total}</p>
              </div>
              <UsersRound className="text-primary" size={24} />
            </CardContent>
          </Card>
          <Card className="border-border bg-card">
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <p className="text-xs uppercase text-muted-foreground">Superusers</p>
                <p className="mt-1 text-2xl font-black">{counts.superusers}</p>
              </div>
              <ShieldCheck className="text-primary" size={24} />
            </CardContent>
          </Card>
          <Card className="border-border bg-card">
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <p className="text-xs uppercase text-muted-foreground">Staff accounts</p>
                <p className="mt-1 text-2xl font-black">{counts.staff}</p>
              </div>
              <UserRound className="text-info" size={24} />
            </CardContent>
          </Card>
          <Card className="border-border bg-card">
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <p className="text-xs uppercase text-muted-foreground">Client accounts</p>
                <p className="mt-1 text-2xl font-black">{counts.clients}</p>
              </div>
              <Handshake className="text-primary" size={24} />
            </CardContent>
          </Card>
        </section>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UsersRound className="text-primary" size={17} />
              User Directory
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Full Name</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Title / Role</TableHead>
                  <TableHead>Access Level</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                      <Loader2 className="mx-auto mb-2 animate-spin text-primary" size={22} />
                      Loading secure directory...
                    </TableCell>
                  </TableRow>
                ) : users.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                      No active users were returned.
                    </TableCell>
                  </TableRow>
                ) : (
                  users.map((entry) => (
                    <TableRow
                      key={entry.id}
                      tabIndex={0}
                      className="cursor-pointer focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                      onClick={() => setSelectedUser(entry)}
                      onKeyDown={(event) => handleRowKeyDown(event, entry)}
                      aria-label={`View ${entry.full_name}`}
                    >
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="flex size-9 items-center justify-center rounded-md bg-primary/15 text-xs font-black text-primary">
                            {getInitials(entry)}
                          </div>
                          <span className="font-bold">{entry.full_name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{entry.username}</TableCell>
                      <TableCell>{entry.email || "Not provided"}</TableCell>
                      <TableCell>{entry.title_role}</TableCell>
                      <TableCell>
                        <Badge variant={getAccessBadgeVariant(entry.access_level)}>
                          {entry.access_level}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Sheet open={selectedUser !== null} onOpenChange={(open) => !open && setSelectedUser(null)}>
        <SheetContent className="w-full border-border bg-card sm:max-w-md">
          {selectedUser && (
            <>
              <SheetHeader className="border-b border-border">
                <div className="mb-3 flex size-14 items-center justify-center rounded-lg bg-primary/15 text-lg font-black text-primary">
                  {getInitials(selectedUser)}
                </div>
                <SheetTitle className="font-mono text-xl font-black">
                  {selectedUser.full_name}
                </SheetTitle>
                <SheetDescription>@{selectedUser.username}</SheetDescription>
              </SheetHeader>
              <div className="space-y-5 overflow-y-auto p-6">
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
                      onClick={() => openEditDialog(selectedUser)}
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
            </>
          )}
        </SheetContent>
      </Sheet>

      <Dialog
        open={editingUser !== null}
        onOpenChange={(open) => {
          if (!open && !isUpdating) {
            setEditingUser(null);
            setEditForm(null);
          }
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto rounded-xl border border-border bg-card sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-lg font-black">
              <Pencil className="text-primary" size={19} />
              Edit User Profile
            </DialogTitle>
            <DialogDescription>
              Update role and identity metadata for @{editingUser?.username}.
            </DialogDescription>
          </DialogHeader>
          {editForm && (
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
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  disabled={isUpdating}
                  onClick={() => {
                    setEditingUser(null);
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
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!isCreating) setIsCreateOpen(open);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto rounded-xl border border-border bg-card sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-lg font-black">
              <ShieldCheck className="text-primary" size={20} />
              Provision New User
            </DialogTitle>
            <DialogDescription>
              Creates a real Django account with a securely hashed password.
            </DialogDescription>
          </DialogHeader>
          <form className="space-y-5" onSubmit={(event) => void handleCreate(event)}>
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
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  autoComplete="off"
                  value={form.username}
                  onChange={updateField("username")}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={updateField("email")}
                  required
                />
              </div>
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
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
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
            <DialogFooter>
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
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
