"use client";

import { categoryOptions } from "@/lib/constants/categories";
import { cn } from "@/lib/utils/cn";

// Cycling pastel tones per chip so the category rail reads as a colorful
// row rather than one flat color repeated — purely decorative, all tokens
// come from this app's own theme (no hardcoded hex).
const categoryTones = [
  {
    selected: "border-pastel-mint/80 bg-pastel-mint text-ink shadow-xs",
    hover: "hover:border-pastel-mint/80 hover:bg-pastel-mint/30 hover:text-ink",
  },
  {
    selected: "border-pastel-sky/80 bg-pastel-sky text-ink shadow-xs",
    hover: "hover:border-pastel-sky/80 hover:bg-pastel-sky/35 hover:text-ink",
  },
  {
    selected: "border-pastel-rose/80 bg-pastel-rose text-ink shadow-xs",
    hover: "hover:border-pastel-rose/80 hover:bg-pastel-rose/35 hover:text-ink",
  },
  {
    selected: "border-pastel-lavender/80 bg-pastel-lavender text-ink shadow-xs",
    hover: "hover:border-pastel-lavender/80 hover:bg-pastel-lavender/35 hover:text-ink",
  },
];

export function CategoryChips({
  value,
  onChange,
  categories,
}: {
  value: string | null;
  onChange: (value: string | null) => void;
  categories?: { slug: string; name: string }[];
}) {
  const options = categories?.map((category) => ({ value: category.slug, label: category.name })) ?? categoryOptions;
  return (
    <div
      role="group"
      aria-label="Filter by category"
      className="flex gap-2 overflow-x-auto pb-1.5 pt-0.5 scrollbar-none [mask-image:linear-gradient(to_right,black_90%,transparent_100%)]"
    >
      <button
        type="button"
        aria-pressed={value === null}
        onClick={() => onChange(null)}
        className={cn(
          "shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-all duration-200 active:scale-95",
          value === null
            ? "border-pastel-lemon/80 bg-pastel-lemon text-ink font-semibold shadow-xs"
            : "border-line bg-surface/90 text-ink-muted hover:border-line-strong hover:bg-pastel-lavender/25 hover:text-ink shadow-xs",
        )}
      >
        All
      </button>

      {options.map((option, index) => {
        const tone = categoryTones[index % categoryTones.length];
        const isSelected = value === option.value;

        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onChange(option.value)}
            className={cn(
              "shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-all duration-200 active:scale-95",
              isSelected
                ? cn(tone.selected, "font-semibold")
                : cn("border-line bg-surface/90 text-ink-muted shadow-xs", tone.hover),
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
