import { z } from "zod";

export const createPoolSchema = z.object({
  name: z.string().min(1, "Name is required").max(100, "Name must be less than 100 characters"),
  description: z.string().max(255, "Description must be less than 255 characters").optional(),
});

export type CreatePoolFormValues = z.infer<typeof createPoolSchema>;

export const updatePoolSchema = z.object({
  name: z.string().min(1, "Name is required").max(100, "Name must be less than 100 characters"),
  description: z.string().max(255, "Description must be less than 255 characters").optional(),
});

export type UpdatePoolFormValues = z.infer<typeof updatePoolSchema>;
