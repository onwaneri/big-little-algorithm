import type { Match } from "../types";

interface Props {
  matches: Match[];
}

export default function MatchesTable({ matches }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
          <tr>
            <th className="px-4 py-3 text-left">Little (Freshman)</th>
            <th className="px-4 py-3 text-left">Big 1</th>
            <th className="px-4 py-3 text-left">Big 2</th>
            <th className="px-4 py-3 text-left">Type</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {matches.map((m) => (
            <tr key={m.freshman} className={m.trio ? "bg-amber-50" : "hover:bg-gray-50"}>
              <td className="px-4 py-2 font-medium text-gray-800">{m.freshman}</td>
              <td className="px-4 py-2 text-gray-700">{m.big_1}</td>
              <td className="px-4 py-2 text-gray-500">{m.big_2 ?? "—"}</td>
              <td className="px-4 py-2">
                {m.trio ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-200 text-amber-800">
                    Trio
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                    Pair
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
