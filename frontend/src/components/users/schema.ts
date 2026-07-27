import { z } from "zod";
import { USER_ACCESS_LEVELS, USER_TITLE_ROLES } from "@/services/api";

const passwordSchema = z
  .string()
  .min(8, { message: "Password must be at least 8 characters long." })
  .regex(/[a-z]/, { message: "Password must contain at least one lowercase letter." })
  .regex(/[A-Z]/, { message: "Password must contain at least one uppercase letter." })
  .regex(/[0-9]/, { message: "Password must contain at least one number." })
  .regex(/[^a-zA-Z0-9]/, { message: "Password must contain at least one special character." });

export const createUserSchema = z.object({
  fullName: z.string().min(1, { message: "Full name is required." }),
  username: z
    .string()
    .min(3, { message: "Username must be at least 3 characters." })
    .regex(/^[a-zA-Z0-9_@+-]+$/, {
      message: "Username can only contain letters, numbers, and @/./+/-/_ characters.",
    }),
  email: z.string().email({ message: "Invalid email address." }),
  titleRole: z.enum(USER_TITLE_ROLES as unknown as [string, ...string[]]),
  accessLevel: z.enum(USER_ACCESS_LEVELS as unknown as [string, ...string[]]),
  password: passwordSchema,
});

export type CreateUserFormValues = z.infer<typeof createUserSchema>;

export const updateUserSchema = z.object({
  fullName: z.string().min(1, { message: "Full name is required." }),
  email: z.string().email({ message: "Invalid email address." }),
  titleRole: z.enum(USER_TITLE_ROLES as unknown as [string, ...string[]]),
  accessLevel: z.enum(USER_ACCESS_LEVELS as unknown as [string, ...string[]]),
});

export type UpdateUserFormValues = z.infer<typeof updateUserSchema>;

export const resetPasswordSchema = z.object({
  password: z
    .string()
    .min(8, { message: "Password must be at least 8 characters." })
    .regex(/[A-Z]/, { message: "Password must contain at least one uppercase letter." })
    .regex(/[a-z]/, { message: "Password must contain at least one lowercase letter." })
    .regex(/[0-9]/, { message: "Password must contain at least one number." })
    .regex(/[^a-zA-Z0-9]/, { message: "Password must contain at least one special character." }),
});

export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;
