import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Merge Tailwind class names safely.
 * Used by all shadcn/ui components.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * I18N-004 FIX: Format a date string to locale display format.
 * Supports both Arabic (ar-SA) and English (en-US) locale conventions.
 * Arabic dates use the Islamic calendar convention when appropriate.
 */
export function formatDate(isoString: string, locale = 'en-US'): string {
  try {
    return new Date(isoString).toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

/**
 * I18N-004 FIX: Format a date to short locale format (no time).
 * Uses Arabic locale conventions for RTL display.
 */
export function formatDateShort(isoString: string, locale = 'en-US'): string {
  try {
    return new Date(isoString).toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    });
  } catch {
    return isoString;
  }
}

/**
 * I18N-003 FIX: Format a number using locale conventions.
 * Arabic uses Eastern Arabic numerals (٠١٢٣...) and different grouping.
 */
export function formatNumber(value: number, locale = 'en-US', options?: Intl.NumberFormatOptions): string {
  try {
    return new Intl.NumberFormat(locale, {
      maximumFractionDigits: 2,
      ...options,
    }).format(value);
  } catch {
    return String(value);
  }
}

/**
 * I18N-003 FIX: Format a currency value using locale conventions.
 */
export function formatCurrency(value: number, locale = 'en-US', currency = 'USD'): string {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return String(value);
  }
}

/**
 * I18N-003 FIX: Format a percentage using locale conventions.
 */
export function formatPercent(value: number, locale = 'en-US'): string {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'percent',
      maximumFractionDigits: 1,
    }).format(value / 100);
  } catch {
    return `${value}%`;
  }
}

/**
 * Truncate a string to maxLength with ellipsis.
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + '...';
}

/**
 * Format bytes to human-readable size.
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Number.parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Debounce a function call.
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * I18N-001 FIX: Get the current document direction (rtl or ltr).
 * Useful for conditional rendering based on text direction.
 */
export function getDirection(): 'rtl' | 'ltr' {
  return document.documentElement.dir === 'rtl' ? 'rtl' : 'ltr';
}

/**
 * I18N-001 FIX: Get the current locale from the document.
 * Falls back to 'en' if not set.
 */
export function getLocale(): string {
  return document.documentElement.lang || 'en';
}
