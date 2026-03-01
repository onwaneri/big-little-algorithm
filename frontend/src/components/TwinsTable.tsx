import type { TwinPair } from "../types";

interface Props {
  twins: TwinPair[];
  freshNames: string[];
  sophNames: string[];
  onChange: (updated: TwinPair[]) => void;
}

const EMPTY: TwinPair = { person_1: "", person_2: "", group: "sophomore" };

export default function TwinsTable({ twins, freshNames, sophNames, onChange }: Props) {
  function update(idx: number, patch: Partial<TwinPair>) {
    onChange(twins.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
  }

  function remove(idx: number) {
    onChange(twins.filter((_, i) => i !== idx));
  }

  function addRow() {
    onChange([...twins, { ...EMPTY }]);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm text-gray-500">
          Pair two people from the same group — the algorithm will find their best shared match.
        </p>
        <button
          onClick={addRow}
          className="text-sm px-3 py-1 rounded-md bg-violet-600 text-white hover:bg-violet-700 transition shrink-0 ml-4"
        >
          + Add twin pair
        </button>
      </div>

      {twins.length === 0 ? (
        <p className="text-sm text-center text-gray-400 italic py-4 border border-dashed border-gray-200 rounded-lg">
          No twin pairs — everyone will be matched individually.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-violet-200 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-violet-50 text-violet-800 uppercase text-xs">
              <tr>
                <th className="px-3 py-2 text-left">Group</th>
                <th className="px-3 py-2 text-left">Person 1</th>
                <th className="px-3 py-2 text-left">Person 2</th>
                <th className="px-2 py-2 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-violet-100">
              {twins.map((tw, idx) => {
                const names = tw.group === "sophomore" ? sophNames : freshNames;
                return (
                  <tr key={idx} className="hover:bg-violet-50">
                    {/* Group toggle */}
                    <td className="px-3 py-1.5">
                      <select
                        value={tw.group}
                        onChange={(e) =>
                          update(idx, {
                            group: e.target.value as "sophomore" | "freshman",
                            person_1: "",
                            person_2: "",
                          })
                        }
                        className="border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-violet-400"
                      >
                        <option value="sophomore">Sophomore</option>
                        <option value="freshman">Freshman</option>
                      </select>
                    </td>
                    {/* Person 1 */}
                    <td className="px-3 py-1.5">
                      <select
                        value={tw.person_1}
                        onChange={(e) => update(idx, { person_1: e.target.value })}
                        className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-violet-400"
                      >
                        <option value="">— select —</option>
                        {names
                          .filter((n) => n !== tw.person_2)
                          .map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </td>
                    {/* Person 2 */}
                    <td className="px-3 py-1.5">
                      <select
                        value={tw.person_2}
                        onChange={(e) => update(idx, { person_2: e.target.value })}
                        className="w-full border border-gray-300 rounded px-1 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-violet-400"
                      >
                        <option value="">— select —</option>
                        {names
                          .filter((n) => n !== tw.person_1)
                          .map((n) => <option key={n} value={n}>{n}</option>)}
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
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
