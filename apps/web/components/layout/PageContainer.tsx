import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

export function PageContainer({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "mx-auto w-full min-w-0 max-w-[1440px] px-4 sm:px-6 xl:px-10",
        className,
      )}
      {...props}
    />
  );
}