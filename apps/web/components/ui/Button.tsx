import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-ink shadow-sm hover:brightness-110 active:scale-[0.98]",
  secondary:
    "bg-pastel-mint text-ink hover:brightness-[0.98] active:scale-[0.98]",
  outline:
    "border border-line-strong bg-surface text-ink hover:bg-surface-sunken active:scale-[0.98]",
  ghost: "text-ink hover:bg-surface-sunken active:scale-[0.98]",
  danger: "bg-danger text-white hover:brightness-110 active:scale-[0.98]",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-9 gap-1.5 rounded-full px-4 text-sm",
  md: "h-11 gap-2 rounded-full px-5 text-sm",
  lg: "h-13 gap-2 rounded-full px-6 text-base",
  icon: "size-10 rounded-full",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading,
      disabled,
      children,
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium transition duration-150",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : null}
        {children}
      </button>
    );
  },
);

Button.displayName = "Button";