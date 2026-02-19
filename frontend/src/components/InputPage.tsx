import { useState } from "react";
import { runMatch } from "../api";
import type { MatchResult, Person } from "../types";
import CSVUpload from "./CSVUpload";
import PersonTable from "./PersonTable";

interface Props {
  onResult: (result: MatchResult) => void;
}

type Tab = "upload" | "manual";

export default function InputPage({ onResult }: Props) {
  const [tab, setTab] = useState<Tab>("upload");
  const [freshmen, setFreshmen] = useState<Person[]>([]);
  const [sophomores, setSophmores] = useState<Person[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const freshNames = freshmen.map((p) => p.name).filter(Boolean);
  const sophNames = sophomores.map((p) => p.name).filter(Boolean);

  async function handleRun() {
    setError(null);

    // Basic client-side validation
    const validFresh = freshmen.filter((p) => p.name.trim());
    const validSoph = sophomores.filter((p) => p.name.trim());

    if (validFresh.length === 0 || validSoph.length === 0) {
      setError("Add at least one freshman and one sophomore before running.");
      return;
    }
    if (validSoph.length - validFresh.length !== 1) {
      setError(
        `There must be exactly 1 more sophomore than freshman. ` +
          `Currently: ${validFresh.length} freshmen, ${validSoph.length} sophomores.`
      );
      return;
    }

    setLoading(true);
    try {
      const result = await runMatch(validFresh, validSoph);
      onResult(result);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "An unexpected error occurred. Make sure the backend is running.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-900">
          Sigma Nu Big-Little Matcher
        </h1>
        <p className="text-gray-500 mt-2">
          Enter preferences, then click <strong>Run Matching</strong> to find the optimal pairings.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        {(["upload", "manual"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2.5 text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "border-b-2 border-indigo-600 text-indigo-700"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "upload" ? "Upload CSVs" : "Manual Entry"}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {tab === "upload" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">
              Freshmen CSV{freshmen.length > 0 ? ` (${freshmen.length} loaded)` : ""}
            </p>
            <CSVUpload
              label="Drop freshmen.csv here"
              onParsed={setFreshmen}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">
              Sophomores CSV{sophomores.length > 0 ? ` (${sophomores.length} loaded)` : ""}
            </p>
            <CSVUpload
              label="Drop sophomores.csv here"
              onParsed={setSophmores}
            />
          </div>
        </div>
      )}

      {/* Loaded data always shows the editable tables */}
      {(tab === "manual" || freshmen.length > 0 || sophomores.length > 0) && (
        <div className="flex gap-6 flex-col lg:flex-row mb-6">
          <PersonTable
            title="Freshmen (Littles)"
            people={freshmen}
            otherNames={sophNames}
            onChange={setFreshmen}
          />
          <PersonTable
            title="Sophomores (Bigs)"
            people={sophomores}
            otherNames={freshNames}
            onChange={setSophmores}
          />
        </div>
      )}

      {/* Count hint */}
      {(freshmen.length > 0 || sophomores.length > 0) && (
        <p className="text-sm text-gray-500 mb-4">
          {freshmen.filter((p) => p.name).length} freshmen &middot;{" "}
          {sophomores.filter((p) => p.name).length} sophomores
          {sophomores.filter((p) => p.name).length -
            freshmen.filter((p) => p.name).length ===
          1 ? (
            <span className="ml-2 text-emerald-600 font-medium">✓ counts look good</span>
          ) : (
            <span className="ml-2 text-amber-600 font-medium">
              ⚠ need exactly 1 more sophomore than freshman
            </span>
          )}
        </p>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Run button */}
      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full py-3 rounded-xl bg-indigo-600 text-white font-semibold text-base hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
      >
        {loading ? "Running algorithm…" : "Run Matching"}
      </button>
    </div>
  );
}
