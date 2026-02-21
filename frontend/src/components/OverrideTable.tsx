import type { OverrideMatch } from "../types";

interface Props {
  overrides: OverrideMatch[];
  freshNames: string[];
  sophNames: string[];
  onChange: (updated: OverrideMatch[]) => void;
}

const EMPTY: OverrideMatch = { freshman_1: "", freshman_2: null, big_1: "", big_2: null };

export default function OverrideTable({ overrides, freshNames, sophNames, onChange }: Props) {
  function update(idx: number, patch: Partial<OverrideMatch>) {
    onChange(overrides.map((ov, i) => (i === idx ? { ...ov, ...patch } : ov)));
  }

  function remove(idx: number) {
    onChange(overrides.filter((_, i) => i !== idx));
  }

  function addRow() {
    onChange([...overrides, { ...EMPTY }]);
  }

  function trioType(ov: OverrideMatch): "duo" | "2big" | "2little" {
    if (ov.big_2) return "2big";
    if (ov.freshman_2) return "2little";
    return "duo";
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm text-gray-500">
          Lock specific matches before the algorithm runs. Each row is removed from
          the available pool.
        </p>
        <button
          onClick={addRow}
          className="text-sm px-3 py-1 rounded-md bg-amber-600 text-white hover:bg-amber-700 transition shrink-0 ml-4"
        >
          + Add override
        </button>
      </div>

      {overrides.length === 0 ? (
        <p className="text-sm text-center text-gray-400 italic py-4 border border-dashed border-gray-200 rounded-lg">
          No overrides — algorithm will match everyone freely.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-amber-200 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-amber-800 uppercase text-xs">
              <tr>
                <th className="px-3 py-2 text-left">Freshman 1</th>
                <th className="px-3 py-2 text-left">Freshman 2 <span className="normal-case font-normal text-amber-600">(2-little trio only)</span></th>
                <th className="px-3 py-2 text-left">Big 1</th>
                <th className="px-3 py-2 text-left">Big 2 <span className="normal-case font-normal text-amber-600">(2-big trio only)</span></th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-2 py-2 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-amber-100">
              {overrides.map((ov, idx) => {
                const type = trioType(ov);
                return (
                  <tr key={idx} className="hover:bg-amber-50">
                    {/* Freshman 1 */}
                    <td className="px-3 py-1.5">
                      <select
                        value={ov.freshman_1}
                        onChange={(e) => update(idx, { freshman_1: e.target.value })}
                        className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-amber-400"
                      >
                        <option value="">— select —</option>
                        {freshNames.map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </td>
                    {/* Freshman 2 */}
                    <td className="px-3 py-1.5">
                      <select
                        value={ov.freshman_2 ?? ""}
                        disabled={!!ov.big_2}
                        onChange={(e) =>
                          update(idx, { freshman_2: e.target.value || null })
                        }
                        className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:opacity-40"
                        title={ov.big_2 ? "Clear Big 2 first to set Freshman 2" : ""}
                      >
                        <option value="">—</option>
                        {freshNames
                          .filter((n) => n !== ov.freshman_1)
                          .map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </td>
                    {/* Big 1 */}
                    <td className="px-3 py-1.5">
                      <select
                        value={ov.big_1}
                        onChange={(e) => update(idx, { big_1: e.target.value })}
                        className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-amber-400"
                      >
                        <option value="">— select —</option>
                        {sophNames.map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </td>
                    {/* Big 2 */}
                    <td className="px-3 py-1.5">
                      <select
                        value={ov.big_2 ?? ""}
                        disabled={!!ov.freshman_2}
                        onChange={(e) =>
                          update(idx, { big_2: e.target.value || null })
                        }
                        className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:opacity-40"
                        title={ov.freshman_2 ? "Clear Freshman 2 first to set Big 2" : ""}
                      >
                        <option value="">—</option>
                        {sophNames
                          .filter((n) => n !== ov.big_1)
                          .map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </td>
                    {/* Type badge */}
                    <td className="px-3 py-1.5">
                      {type === "duo" && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Duo</span>
                      )}
                      {type === "2big" && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-200 text-amber-800">2-Big Trio</span>
                      )}
                      {type === "2little" && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-violet-200 text-violet-800">2-Little Trio</span>
                      )}
                    </td>
                    {/* Delete */}
                    <td className="px-2 py-1.5 text-center">
                      <button
                        onClick={() => remove(idx)}
                        className="text-red-400 hover:text-red-600 text-base leading-none"
                        title="Remove"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
