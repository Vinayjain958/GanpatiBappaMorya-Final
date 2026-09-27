import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { ProviderInsightStat } from "@/types/provider";
import { Card, CardBody } from "@/components/ui/Card";
import { cn } from "@/lib/utils/cn";

const trendIcon = { up: TrendingUp, down: TrendingDown, flat: Minus };

export function InsightStatCard({ stat }: { stat: ProviderInsightStat }) {
  const TrendIcon = stat.trend ? trendIcon[stat.trend] : null;

  return (
    <Card className="h-full">
      <CardBody className="flex min-h-36 flex-col items-start gap-2 p-5">
        <p className="text-sm font-medium text-ink-muted">{stat.label}</p>
        <p className="text-3xl font-semibold tracking-tight text-ink">{stat.value}</p>

        {stat.changeLabel ? (
          <p
            className={cn(
              "mt-auto inline-flex items-center gap-1 rounded-full bg-surface-raised px-2.5 py-1 text-xs font-medium",
              stat.trend === "up" && "bg-success-soft text-success",
              stat.trend === "down" && "bg-danger-soft text-danger",
              (!stat.trend || stat.trend === "flat") && "text-ink-subtle",
            )}
          >
            {TrendIcon ? <TrendIcon className="size-3.5" aria-hidden="true" /> : null}
            {stat.changeLabel}
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}