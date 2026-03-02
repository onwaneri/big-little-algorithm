import type { BannedPair } from "../types";

interface Props {
  banned: BannedPair[];
  littleNames: string[];
  bigNames: string[];
  onChange: (updated: BannedPair[]) => void;
}

const EMPTY: BannedPair = { little: "", big: "" };

export default function BannedPairsTable({ banned, littleNames, bigNames, onChange }: Props) {
  function update(idx: number, patch: Partial<BannedPair>) {
    onChange(banned.map((b, i) => (i === idx ? { ...b, ...patch } : b)));
  }

  function remove(idx: number) {
    onChange(banned.filter((_, i) => i !== idx));
  }

  function addRow() {
    onChange([...banned, { ...EMPTY }]);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm text-gray-500">
          Specify little-big pairs that should NOT be matched together.
        </p>
        <button
          onClick={addRow}
          className="text-sm px-3 py-1 rounded-md bg-red-600 text-white hover:bg-red-700 transition shrink-0 ml-4"
        >
          + Add banned pair
        </button>
      </div>

      {banned.length === 0 ? (
        <p className="text-sm text-center text-gray-400 italic py-4 border border-dashed border-gray-200 rounded-lg">
          No banned pairs — all little-big matches are allowed.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-red-200 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-red-50 text-red-800 uppercase text-xs">
              <tr>
                <th className="px-3 py-2 text-left">Little</th>
                <th className="px-3 py-2 text-left">Big</th>
                <th className="px-2 py-2 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-red-100">
              {banned.map((ban, idx) => (
                <tr key={idx} className="hover:bg-red-50">
                  {/* Little */}
                  <td className="px-3 py-1.5">
                    <select
                      value={ban.little}
                      onChange={(e) => update(idx, { little: e.target.value })}
                      className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-red-400"
                    >
                      <option value="">— select —</option>
                      {littleNames
                        .filter((n) => n !== ban.big)
                        .map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                    </select>
                  </td>
                  {/* Big */}
                  <td className="px-3 py-1.5">
                    <select
                      value={ban.big}
                      onChange={(e) => update(idx, { big: e.target.value })}
                      className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-red-400"
                    >
                      <option value="">— select —</option>
                      {bigNames
                        .filter((n) => n !== ban.little)
                        .map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                    </select>
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
