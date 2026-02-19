import type { MatchResult } from "../types";
import MatchesTable from "./MatchesTable";
import SatisfactionTable from "./SatisfactionTable";
import SummaryStats from "./SummaryStats";

interface Props {
  result: MatchResult;
  onBack: () => void;
}

export default function ResultsPage({ result, onBack }: Props) {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Matching Results</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {result.matches.length} pairings ·{" "}
            {result.matches.filter((m) => m.trio).length === 1 ? "1 trio" : "no trio"}
          </p>
        </div>
        <button
          onClick={onBack}
          className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition text-sm font-medium"
        >
          ← Back / Re-run
        </button>
      </div>

      {/* Summary cards */}
      <SummaryStats
        summary={result.summary}
        totalPairs={result.matches.length}
      />

      {/* Final matches */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Final Pairings</h2>
        <MatchesTable matches={result.matches} />
      </section>

      {/* Satisfaction scores */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Satisfaction Scores</h2>
        <p className="text-xs text-gray-500 mb-3">
          Colors: <span className="text-emerald-700 font-semibold">green ≥ 80%</span>{" "}
          &middot;{" "}
          <span className="text-amber-600 font-semibold">yellow 40–79%</span>{" "}
          &middot;{" "}
          <span className="text-red-600 font-semibold">red &lt; 40%</span>
        </p>
        <SatisfactionTable rows={result.satisfaction} />
      </section>
    </div>
  );
}
