"use client";

import { ArrowUpDown, ChevronDown, Clock, Database, MapPinned, Wallet } from "lucide-react";
import { budgetOptions, durationOptions } from "@/lib/constants/categories";
import type { DiscoverySort } from "@/types/api";
import type { BudgetOption, DiscoveryDataSource, DurationOption } from "@/types/discovery";

const sortOptions: { value: DiscoverySort; label: string }[] = [
  { value: "relevance", label: "Relevance" },
  { value: "distance", label: "Nearest" },
  { value: "price", label: "Price: low to high" },
  { value: "duration", label: "Duration: shortest" },
  { value: "newest", label: "Newest" },
];

function FilterSelect<T extends string>({
  icon: Icon,
  label,
  value,
  options,
  onChange,
  disabledOptionValues,
}: {
  icon: typeof Clock;
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  disabledOptionValues?: T[];
}) {
  return (
    <label className="relative inline-flex items-center gap-2 rounded-full border border-line bg-surface/90 px-3 py-1.5 text-sm text-ink-muted shadow-xs transition-all duration-150 hover:border-line-strong hover:bg-surface focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/10">
      <Icon className="size-3.5 shrink-0 text-accent" aria-hidden="true" />
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className="min-w-0 max-w-[190px] cursor-pointer appearance-none bg-transparent pr-4 text-xs font-medium text-ink focus:outline-none"
        aria-label={label}
      >
        {options.map((option) => (
          <option
            key={option.value}
            value={option.value}
            disabled={disabledOptionValues?.includes(option.value)}
          >
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 size-3 text-ink-subtle" aria-hidden="true" />
    </label>
  );
}

export interface FilterBarValue {
  budget: BudgetOption;
  duration: DurationOption;
  sort: DiscoverySort;
  dataSource: DiscoveryDataSource;
}

export function FilterBar({
  value,
  onChange,
  hasLocation,
}: {
  value: FilterBarValue;
  onChange: (value: FilterBarValue) => void;
  hasLocation: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <FilterSelect
        icon={Wallet}
        label="Budget"
        value={value.budget}
        options={budgetOptions as { value: BudgetOption; label: string }[]}
        onChange={(budget) => onChange({ ...value, budget })}
      />

      <FilterSelect
        icon={Clock}
        label="Duration"
        value={value.duration}
        options={durationOptions as { value: DurationOption; label: string }[]}
        onChange={(duration) => onChange({ ...value, duration })}
      />

      <FilterSelect
        icon={ArrowUpDown}
        label="Sort"
        value={value.sort}
        options={sortOptions}
        onChange={(sort) => onChange({ ...value, sort })}
        disabledOptionValues={
          hasLocation ? [] : (["distance"] as DiscoverySort[])
        }
      />

      <FilterSelect
        icon={Database}
        label="Data source"
        value={value.dataSource}
        options={[
          { value: "all", label: "All listings" },
          { value: "source", label: "Non-demo records" },
          { value: "demo", label: "Demo records only" },
        ]}
        onChange={(dataSource) => onChange({ ...value, dataSource })}
      />

      {!hasLocation ? (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-pastel-lemon/80 bg-pastel-lemon/40 px-3 py-1.5 text-xs font-medium text-ink shadow-xs">
          <MapPinned className="size-3.5 shrink-0" aria-hidden="true" />
          Set a location to sort by distance
        </span>
      ) : null}
      {value.dataSource === "source" ? (
        <span className="basis-full text-xs text-ink-subtle">
          Source-derived places can include estimated price and duration. They are not a claim that an activity is bookable.
        </span>
      ) : null}
    </div>
  );
}
