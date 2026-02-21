import type { SatisfactionRow } from "../types";

interface Props {
  rows: SatisfactionRow[];
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-700 font-semibold";
  if (score >= 40) return "text-amber-600 font-semibold";
  return "text-red-600 font-semibold";
}

function ScoreCell({ value }: { value: number | null }) {
  if (value === null) return <td className="px-3 py-2 text-gray-300 text-center">—</td>;
  return (
    <td className={`px-3 py-2 text-center ${scoreColor(value)}`}>
      {value.toFixed(0)}%
    </td>
  );
}

export default function SatisfactionTable({ rows }: Props) {
  const has2little = rows.some((r) => r.freshman_2);

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
          <tr>
            <th className="px-4 py-3 text-left">Little 1</th>
            {has2little && <th className="px-4 py-3 text-left">Little 2</th>}
            <th className="px-4 py-3 text-left">Big 1</th>
            <th className="px-4 py-3 text-left">Big 2</th>
            <th className="px-3 py-3 text-center">Little 1 %</th>
            {has2little && <th className="px-3 py-3 text-center">Little 2 %</th>}
            <th className="px-3 py-3 text-center">Big 1 %</th>
            <th className="px-3 py-3 text-center">Big 2 %</th>
            <th className="px-3 py-3 text-center">Pair Score</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((r, idx) => (
            <tr key={idx} className={(r.big_2 || r.freshman_2) ? "bg-amber-50" : "hover:bg-gray-50"}>
              <td className="px-4 py-2 font-medium text-gray-800">{r.freshman}</td>
              {has2little && (
                <td className="px-4 py-2 text-gray-700">{r.freshman_2 ?? "—"}</td>
              )}
              <td className="px-4 py-2 text-gray-700">{r.big_1}</td>
              <td className="px-4 py-2 text-gray-500">{r.big_2 ?? "—"}</td>
              <ScoreCell value={r.freshman_score} />
              {has2little && <ScoreCell value={r.freshman_2_score} />}
              <ScoreCell value={r.big_1_score} />
              <ScoreCell value={r.big_2_score} />
              <td className="px-3 py-2 text-center font-mono text-gray-700">
                {r.pair_score.toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
