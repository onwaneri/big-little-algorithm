import type { Summary } from "../types";

interface Props {
  summary: Summary;
  totalPairs: number;
}

export default function SummaryStats({ summary, totalPairs }: Props) {
  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      <StatCard
        label="Median Pair Score"
        value={`${summary.median_pair_score.toFixed(1)}`}
        sub="out of 110"
        color="indigo"
      />
      <StatCard
        label="Average Pair Score"
        value={`${summary.average_pair_score.toFixed(1)}`}
        sub="out of 110"
        color="violet"
      />
      <StatCard
        label="Mutual Matches"
        value={`${summary.mutual_count} / ${totalPairs}`}
        sub="both ≥ 80%"
        color="emerald"
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: "indigo" | "violet" | "emerald";
}) {
  const ring = {
    indigo: "ring-indigo-200 bg-indigo-50",
    violet: "ring-violet-200 bg-violet-50",
    emerald: "ring-emerald-200 bg-emerald-50",
  }[color];
  const text = {
    indigo: "text-indigo-700",
    violet: "text-violet-700",
    emerald: "text-emerald-700",
  }[color];

  return (
    <div className={`rounded-xl ring-1 ${ring} p-4 text-center`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
        {label}
      </p>
      <p className={`text-3xl font-bold ${text}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  );
}
