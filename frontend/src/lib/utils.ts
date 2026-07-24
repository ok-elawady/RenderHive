import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function generateSecurePassword(): string {
  const uppers = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const lowers = "abcdefghijklmnopqrstuvwxyz";
  const numbers = "0123456789";
  const specials = "!@#$%^&*()_+";
  const all = uppers + lowers + numbers + specials;
  
  const pwdArray = [
    uppers[Math.floor(Math.random() * uppers.length)],
    lowers[Math.floor(Math.random() * lowers.length)],
    numbers[Math.floor(Math.random() * numbers.length)],
    specials[Math.floor(Math.random() * specials.length)],
  ];
  
  for (let i = 4; i < 16; i++) {
    pwdArray.push(all[Math.floor(Math.random() * all.length)]);
  }
  
  // Shuffle the array to avoid predictable character positions
  for (let i = pwdArray.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pwdArray[i], pwdArray[j]] = [pwdArray[j], pwdArray[i]];
  }
  
  return pwdArray.join("");
}
