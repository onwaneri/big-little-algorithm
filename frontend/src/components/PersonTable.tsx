import type { Person } from "../types";

interface Props {
  title: string;
  people: Person[];
  otherNames: string[]; // names from the other group, for preference dropdowns
  onChange: (updated: Person[]) => void;
  numPreferences: number;
}

export default function PersonTable({ title, people, otherNames, onChange, numPreferences }: Props) {
  function updateName(idx: number, name: string) {
    const next = people.map((p, i) => (i === idx ? { ...p, name } : p));
    onChange(next);
  }

  function updatePref(idx: number, prefIdx: number, value: string) {
    const next = people.map((p, i) => {
      if (i !== idx) return p;
      const prefs = [...p.preferences];
      prefs[prefIdx] = value;
      // Remove empty trailing slots
      while (prefs.length > 0 && prefs[prefs.length - 1] === "") prefs.pop();
      return { ...p, preferences: prefs };
    });
    onChange(next);
  }

  function addRow() {
    onChange([...people, { name: "", preferences: [] }]);
  }

  function removeRow(idx: number) {
    onChange(people.filter((_, i) => i !== idx));
  }

  // Names already used by a person at position `prefIdx` across all rows (for filtering)
  function usedInRow(person: Person, prefIdx: number): Set<string> {
    const used = new Set<string>();
    person.preferences.forEach((p, i) => {
      if (i !== prefIdx && p) used.add(p);
    });
    return used;
  }

  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-800">
          {title}{" "}
          <span className="text-sm font-normal text-gray-500">({people.length})</span>
        </h2>
        <button
          onClick={addRow}
          className="text-sm px-3 py-1 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 transition"
        >
          + Add
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
            <tr>
              <th className="px-3 py-2 text-left w-36">Name</th>
              {Array.from({ length: numPreferences }, (_, i) => (
                <th key={i} className="px-2 py-2 text-left">#{i + 1}</th>
              ))}
              <th className="px-2 py-2 w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {people.map((person, idx) => {
              return (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-3 py-1.5">
                    <input
                      type="text"
                      value={person.name}
                      onChange={(e) => updateName(idx, e.target.value)}
                      placeholder="Full name"
                      className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </td>
                  {Array.from({ length: numPreferences }, (_, prefIdx) => {
                    const current = person.preferences[prefIdx] ?? "";
                    const rowUsed = usedInRow(person, prefIdx);
                    return (
                      <td key={prefIdx} className="px-2 py-1.5">
                        <select
                          value={current}
                          onChange={(e) => updatePref(idx, prefIdx, e.target.value)}
                          className="w-full border border-gray-300 rounded px-1 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
                        >
                          <option value="">—</option>
                          {otherNames
                            .filter((n) => n === current || !rowUsed.has(n))
                            .map((n) => (
                              <option key={n} value={n}>
                                {n}
                              </option>
                            ))}
                        </select>
                      </td>
                    );
                  })}
                  <td className="px-2 py-1.5 text-center">
                    <button
                      onClick={() => removeRow(idx)}
                      className="text-red-400 hover:text-red-600 text-base leading-none"
                      title="Remove"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              );
            })}
            {people.length === 0 && (
              <tr>
                <td
                  colSpan={numPreferences + 2}
                  className="px-4 py-6 text-center text-gray-400 italic"
                >
                  No entries yet. Click "+ Add" or upload a CSV.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
