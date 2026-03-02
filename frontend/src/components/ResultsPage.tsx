import type { MatchResult } from "../types";
import MatchesTable from "./MatchesTable";
import SatisfactionTable from "./SatisfactionTable";
import SummaryStats from "./SummaryStats";

interface Props {
  result: MatchResult;
  onEditConstraints: () => void;
}

export default function ResultsPage({ result, onEditConstraints }: Props) {

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
        <div className="flex gap-2">
          <button
            onClick={onEditConstraints}
            className="px-4 py-2 rounded-lg border border-indigo-300 text-indigo-700 hover:bg-indigo-50 transition text-sm font-medium"
          >
            ✏ Edit constraints
          </button>
          <button
            onClick={onEditConstraints}
            className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition text-sm font-medium"
          >
            ← Back
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <SummaryStats
        summary={result.summary}
        totalPairs={result.matches.length}
      />

      {/* Unmatched people (only shown when config allowed leaving people out) */}
      {(result.unmatched_bigs.length > 0 || result.unmatched_littles.length > 0) && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Unmatched</h2>
          <div className="flex flex-col sm:flex-row gap-4">
            {result.unmatched_bigs.length > 0 && (
              <div className="flex-1 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase text-amber-700 mb-2">
                  Bigs without a little ({result.unmatched_bigs.length})
                </p>
                <ul className="space-y-1">
                  {result.unmatched_bigs.map((name) => (
                    <li key={name} className="text-sm text-amber-900">{name}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.unmatched_littles.length > 0 && (
              <div className="flex-1 rounded-lg border border-violet-200 bg-violet-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase text-violet-700 mb-2">
                  Littles without a big ({result.unmatched_littles.length})
                </p>
                <ul className="space-y-1">
                  {result.unmatched_littles.map((name) => (
                    <li key={name} className="text-sm text-violet-900">{name}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

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
