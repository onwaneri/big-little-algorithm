import { useState } from "react";
import type { Match } from "../types";

interface Props {
  matches: Match[];
  allLittles: string[];
  allBigs: string[];
  onApply: (editedMatches: Match[]) => void;
  isLoading?: boolean;
}

export default function EditableMatchesTable({
  matches,
  allLittles,
  allBigs,
  onApply,
  isLoading = false,
}: Props) {
  const [edited, setEdited] = useState<Match[]>(matches);
  const [hasChanges, setHasChanges] = useState(false);
  const has2little = edited.some((m) => m.little_2);

  function updateMatch(idx: number, patch: Partial<Match>) {
    const updated = edited.map((m, i) =>
      i === idx ? { ...m, ...patch } : m
    );
    setEdited(updated);
    setHasChanges(true);
  }

  function handleApply() {
    onApply(edited);
    setHasChanges(false);
  }

  function handleReset() {
    setEdited(matches);
    setHasChanges(false);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-600">
          Click cells to edit matches. Apply changes to re-run with your custom overrides.
        </p>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            disabled={!hasChanges || isLoading}
            className="text-sm px-3 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            Reset
          </button>
          <button
            onClick={handleApply}
            disabled={!hasChanges || isLoading}
            className="text-sm px-3 py-1.5 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {isLoading ? "Re-running..." : "Apply Changes & Re-run"}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">Little 1</th>
              {has2little && <th className="px-4 py-3 text-left">Little 2</th>}
              <th className="px-4 py-3 text-left">Big 1</th>
              <th className="px-4 py-3 text-left">Big 2</th>
              <th className="px-4 py-3 text-left">Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {edited.map((m, idx) => (
              <tr key={idx} className={m.trio ? "bg-amber-50" : "hover:bg-gray-50"}>
                {/* Little 1 */}
                <td className="px-4 py-2">
                  <select
                    value={m.little}
                    onChange={(e) => updateMatch(idx, { little: e.target.value })}
                    className="w-full border border-gray-300 rounded px-2 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  >
                    {allLittles.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </td>
                {/* Little 2 */}
                {has2little && (
                  <td className="px-4 py-2">
                    {m.little_2 ? (
                      <select
                        value={m.little_2}
                        onChange={(e) => updateMatch(idx, { little_2: e.target.value })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-indigo-400"
                      >
                        {allLittles.map((f) => (
                          <option key={f} value={f}>
                            {f}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                )}
                {/* Big 1 */}
                <td className="px-4 py-2">
                  <select
                    value={m.big_1}
                    onChange={(e) => updateMatch(idx, { big_1: e.target.value })}
                    className="w-full border border-gray-300 rounded px-2 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  >
                    {allBigs.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                {/* Big 2 */}
                <td className="px-4 py-2">
                  {m.big_2 ? (
                    <select
                      value={m.big_2}
                      onChange={(e) => updateMatch(idx, { big_2: e.target.value })}
                      className="w-full border border-gray-300 rounded px-2 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    >
                      {allBigs.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-gray-500">—</span>
                  )}
                </td>
                {/* Type badge */}
                <td className="px-4 py-2">
                  {!m.trio ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                      Duo
                    </span>
                  ) : m.big_2 ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-200 text-amber-800">
                      2-Big Trio
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-violet-200 text-violet-800">
                      2-Little Trio
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
