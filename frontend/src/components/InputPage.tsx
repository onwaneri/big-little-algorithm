import { useState } from "react";
import { parseOverridesCSV, runMatch } from "../api";
import type { MatchResult, OverrideMatch, Person } from "../types";
import CSVUpload from "./CSVUpload";
import OverrideTable from "./OverrideTable";
import PersonTable from "./PersonTable";

interface Props {
  onResult: (result: MatchResult) => void;
}

type Tab = "upload" | "manual";

export default function InputPage({ onResult }: Props) {
  const [tab, setTab] = useState<Tab>("upload");
  const [freshmen, setFreshmen] = useState<Person[]>([]);
  const [sophomores, setSophmores] = useState<Person[]>([]);
  const [overrides, setOverrides] = useState<OverrideMatch[]>([]);
  const [showOverrides, setShowOverrides] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [overrideUploadMsg, setOverrideUploadMsg] = useState<string | null>(null);

  const freshNames = freshmen.map((p) => p.name).filter(Boolean);
  const sophNames = sophomores.map((p) => p.name).filter(Boolean);

  const validFresh = freshmen.filter((p) => p.name.trim());
  const validSoph  = sophomores.filter((p) => p.name.trim());
  const freshCount = validFresh.length;
  const sophCount  = validSoph.length;
  const D = sophCount - freshCount;
  const absDiff = Math.abs(D);

  function trioHint(): { text: string; ok: boolean } {
    if (freshCount === 0 || sophCount === 0) return { text: "", ok: false };
    if (D === 0) return { text: "✓ Equal counts — pure 1-to-1, no trios", ok: true };
    if (D > 0) return { text: `✓ ${absDiff} trio${absDiff > 1 ? "s" : ""} of (1 little + 2 bigs)`, ok: true };
    return { text: `✓ ${absDiff} trio${absDiff > 1 ? "s" : ""} of (2 littles + 1 big)`, ok: true };
  }

  async function handleOverrideCSV(file: File) {
    try {
      const parsed = await parseOverridesCSV(file);
      setOverrides(parsed);
      setOverrideUploadMsg(`Loaded ${parsed.length} override(s) from ${file.name}`);
    } catch {
      setOverrideUploadMsg("Failed to parse overrides CSV.");
    }
  }

  async function handleRun() {
    setError(null);
    if (freshCount === 0 || sophCount === 0) {
      setError("Add at least one freshman and one sophomore before running.");
      return;
    }

    // Validate overrides reference known names
    for (const ov of overrides) {
      if (!freshNames.includes(ov.freshman_1)) {
        setError(`Override error: '${ov.freshman_1}' is not in the freshmen list.`);
        return;
      }
      if (ov.freshman_2 && !freshNames.includes(ov.freshman_2)) {
        setError(`Override error: '${ov.freshman_2}' is not in the freshmen list.`);
        return;
      }
      if (!sophNames.includes(ov.big_1)) {
        setError(`Override error: '${ov.big_1}' is not in the sophomores list.`);
        return;
      }
      if (ov.big_2 && !sophNames.includes(ov.big_2)) {
        setError(`Override error: '${ov.big_2}' is not in the sophomores list.`);
        return;
      }
    }

    setLoading(true);
    try {
      const result = await runMatch(validFresh, validSoph, overrides);
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

  const hint = trioHint();

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-900">Sigma Nu Big-Little Matcher</h1>
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
            <CSVUpload label="Drop freshmen.csv here" onParsed={setFreshmen} />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">
              Sophomores CSV{sophomores.length > 0 ? ` (${sophomores.length} loaded)` : ""}
            </p>
            <CSVUpload label="Drop sophomores.csv here" onParsed={setSophmores} />
          </div>
        </div>
      )}

      {/* Editable tables (always shown once data exists, or in manual mode) */}
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
      {(freshCount > 0 || sophCount > 0) && (
        <p className="text-sm text-gray-500 mb-4">
          {freshCount} freshman{freshCount !== 1 ? "en" : ""} &middot; {sophCount} sophomore{sophCount !== 1 ? "s" : ""}
          {hint.text && (
            <span className={`ml-2 font-medium ${hint.ok ? "text-emerald-600" : "text-amber-600"}`}>
              {hint.text}
            </span>
          )}
        </p>
      )}

      {/* Manual overrides section */}
      <div className="mb-6">
        <button
          onClick={() => setShowOverrides((v) => !v)}
          className="flex items-center gap-2 text-sm font-medium text-amber-700 hover:text-amber-900 transition mb-2"
        >
          <span>{showOverrides ? "▾" : "▸"}</span>
          Lock specific matches (manual overrides)
          {overrides.length > 0 && (
            <span className="ml-1 px-2 py-0.5 rounded-full bg-amber-200 text-amber-800 text-xs">
              {overrides.length}
            </span>
          )}
        </button>

        {showOverrides && (
          <div className="pl-4 border-l-2 border-amber-200">
            {/* Override CSV upload */}
            <div className="mb-4">
              <p className="text-xs text-gray-500 mb-1">
                Upload an overrides CSV (columns: <code>Freshman_1, Freshman_2, Big_1, Big_2</code> — leave optional columns empty).
              </p>
              <label className="inline-block cursor-pointer text-sm px-3 py-1.5 rounded-md border border-amber-300 text-amber-700 hover:bg-amber-50 transition">
                Upload overrides.csv
                <input
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleOverrideCSV(f);
                  }}
                />
              </label>
              {overrideUploadMsg && (
                <span className="ml-3 text-xs text-gray-500">{overrideUploadMsg}</span>
              )}
            </div>

            <OverrideTable
              overrides={overrides}
              freshNames={freshNames}
              sophNames={sophNames}
              onChange={setOverrides}
            />
          </div>
        )}
      </div>

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
