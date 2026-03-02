import { useState } from "react";
import { parseOverridesCSV, runMatch } from "../api";
import type { MatchConfig, MatchResult, OverrideMatch, Person, TwinPair, BannedPair } from "../types";
import CSVUpload from "./CSVUpload";
import OverrideTable from "./OverrideTable";
import PersonTable from "./PersonTable";
import TwinsTable from "./TwinsTable";
import BannedPairsTable from "./BannedPairsTable";

interface Props {
  onResult: (
    result: MatchResult,
    littles: Person[],
    bigs: Person[],
    overrides: OverrideMatch[],
    twins: TwinPair[],
    banned: BannedPair[],
    config: MatchConfig
  ) => void;
  initialLittles?: Person[];
  initialBigs?: Person[];
  initialOverrides?: OverrideMatch[];
  initialTwins?: TwinPair[];
  initialBanned?: BannedPair[];
  initialConfig?: MatchConfig;
}

type Tab = "upload" | "manual";

const DEFAULT_CONFIG: MatchConfig = {
  everyBigNeedsLittle: null,
  everyLittleNeedsBig: null,
  numPreferences: null,
  bigWeight: 0.5,
};

export default function InputPage({
  onResult,
  initialLittles = [],
  initialBigs = [],
  initialOverrides = [],
  initialTwins = [],
  initialBanned = [],
  initialConfig = DEFAULT_CONFIG,
}: Props) {
  const [tab, setTab] = useState<Tab>("upload");
  const [littles, setLittles] = useState<Person[]>(initialLittles);
  const [bigs, setBigs] = useState<Person[]>(initialBigs);
  const [overrides, setOverrides] = useState<OverrideMatch[]>(initialOverrides);
  const [twins, setTwins] = useState<TwinPair[]>(initialTwins);
  const [banned, setBanned] = useState<BannedPair[]>(initialBanned);
  const [config, setConfig] = useState<MatchConfig>(initialConfig);
  const [showOverrides, setShowOverrides] = useState(false);
  const [showTwins, setShowTwins] = useState(false);
  const [showBanned, setShowBanned] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [overrideUploadMsg, setOverrideUploadMsg] = useState<string | null>(null);

  const littleNames = littles.map((p) => p.name).filter(Boolean);
  const bigNames    = bigs.map((p) => p.name).filter(Boolean);

  const validLittles = littles.filter((p) => p.name.trim());
  const validBigs    = bigs.filter((p) => p.name.trim());
  const littleCount  = validLittles.length;
  const bigCount     = validBigs.length;
  const D = bigCount - littleCount;
  const absDiff = Math.abs(D);

  // Config is complete when all required questions are answered
  const configComplete =
    config.everyBigNeedsLittle !== null &&
    config.everyLittleNeedsBig !== null &&
    config.numPreferences !== null &&
    config.numPreferences > 0;

  function trioHint(): { text: string; ok: boolean } {
    if (littleCount === 0 || bigCount === 0) return { text: "", ok: false };
    if (D === 0) return { text: "Equal counts — pure 1-to-1, no trios", ok: true };
    if (D > 0) {
      if (config.everyBigNeedsLittle === false) {
        return { text: `${absDiff} big${absDiff > 1 ? "s" : ""} will go unmatched`, ok: true };
      }
      return { text: `${absDiff} trio${absDiff > 1 ? "s" : ""} of (1 little + 2 bigs)`, ok: true };
    }
    if (config.everyLittleNeedsBig === false) {
      return { text: `${absDiff} little${absDiff > 1 ? "s" : ""} will go unmatched`, ok: true };
    }
    return { text: `${absDiff} trio${absDiff > 1 ? "s" : ""} of (2 littles + 1 big)`, ok: true };
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
    if (littleCount === 0 || bigCount === 0) {
      setError("Add at least one little and one big before running.");
      return;
    }
    if (!configComplete) {
      setError("Please answer all configuration questions before running.");
      return;
    }

    // Validate twin pairs
    for (const tw of twins) {
      if (!tw.person_1 || !tw.person_2) {
        setError("Each twin pair must have both people selected.");
        return;
      }
      const list = tw.group === "big" ? bigNames : littleNames;
      if (!list.includes(tw.person_1)) {
        setError(`Twin error: '${tw.person_1}' is not in the ${tw.group}s list.`);
        return;
      }
      if (!list.includes(tw.person_2)) {
        setError(`Twin error: '${tw.person_2}' is not in the ${tw.group}s list.`);
        return;
      }
    }

    // Validate banned pairs
    for (const ban of banned) {
      if (!ban.little || !ban.big) {
        setError("Each banned pair must have both a little and big selected.");
        return;
      }
      if (!littleNames.includes(ban.little)) {
        setError(`Banned pair error: '${ban.little}' is not in the littles list.`);
        return;
      }
      if (!bigNames.includes(ban.big)) {
        setError(`Banned pair error: '${ban.big}' is not in the bigs list.`);
        return;
      }
    }

    // Validate overrides reference known names
    for (const ov of overrides) {
      if (!littleNames.includes(ov.little_1)) {
        setError(`Override error: '${ov.little_1}' is not in the littles list.`);
        return;
      }
      if (ov.little_2 && !littleNames.includes(ov.little_2)) {
        setError(`Override error: '${ov.little_2}' is not in the littles list.`);
        return;
      }
      if (!bigNames.includes(ov.big_1)) {
        setError(`Override error: '${ov.big_1}' is not in the bigs list.`);
        return;
      }
      if (ov.big_2 && !bigNames.includes(ov.big_2)) {
        setError(`Override error: '${ov.big_2}' is not in the bigs list.`);
        return;
      }
    }

    setLoading(true);
    try {
      const result = await runMatch(validLittles, validBigs, overrides, twins, banned, config);
      onResult(result, validLittles, validBigs, overrides, twins, banned, config);
    } catch (err: unknown) {
      type AxiosErr = { response?: { status?: number; data?: { detail?: unknown } }; message?: string };
      const e = err as AxiosErr;
      let detail: string;
      if (e.response) {
        const d = e.response.data?.detail;
        detail = Array.isArray(d)
          ? d.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join("; ")
          : d != null
          ? String(d)
          : `HTTP ${e.response.status ?? "?"} — no detail returned`;
      } else {
        detail = e.message
          ? `Network error: ${e.message}`
          : "Cannot reach the server — check Render logs.";
      }
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  const hint = trioHint();
  const numPrefs = config.numPreferences ?? 5;

  function YesNoToggle({
    value,
    onChange,
  }: {
    value: boolean | null;
    onChange: (v: boolean) => void;
  }) {
    return (
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(true)}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium border transition ${
            value === true
              ? "bg-emerald-600 text-white border-emerald-600"
              : "bg-white text-gray-600 border-gray-300 hover:border-emerald-400"
          }`}
        >
          Yes
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium border transition ${
            value === false
              ? "bg-red-500 text-white border-red-500"
              : "bg-white text-gray-600 border-gray-300 hover:border-red-400"
          }`}
        >
          No
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-900">Big-Little Matching</h1>
        <p className="text-gray-500 mt-2">
          Enter preferences, then click <strong>Run Matching</strong> to find the optimal pairings.
        </p>
      </div>

      {/* ── Matching Configuration (mandatory) ── */}
      <div className="mb-8 rounded-xl border border-indigo-200 bg-indigo-50 p-5">
        <h2 className="text-base font-semibold text-indigo-900 mb-4">
          Matching Configuration
          <span className="ml-2 text-xs font-normal text-indigo-600">(required before running)</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Q1: Does every big need a little? */}
          <div>
            <p className="text-sm font-medium text-gray-800 mb-2">
              Does every big need a little?
            </p>
            <p className="text-xs text-gray-500 mb-2">
              If <strong>No</strong>, surplus bigs remain unmatched instead of sharing a little.
            </p>
            <YesNoToggle
              value={config.everyBigNeedsLittle}
              onChange={(v) => setConfig((c) => ({ ...c, everyBigNeedsLittle: v }))}
            />
          </div>

          {/* Q2: Does every little need a big? */}
          <div>
            <p className="text-sm font-medium text-gray-800 mb-2">
              Does every little need a big?
            </p>
            <p className="text-xs text-gray-500 mb-2">
              If <strong>No</strong>, surplus littles remain unmatched instead of sharing a big.
            </p>
            <YesNoToggle
              value={config.everyLittleNeedsBig}
              onChange={(v) => setConfig((c) => ({ ...c, everyLittleNeedsBig: v }))}
            />
          </div>

          {/* Q3: How many preference rankings? */}
          <div>
            <p className="text-sm font-medium text-gray-800 mb-2">
              How many preferences can each person rank?
            </p>
            <p className="text-xs text-gray-500 mb-2">
              Sets the number of preference slots (1–10). Used for scoring.
            </p>
            <input
              type="number"
              min={1}
              max={10}
              value={config.numPreferences ?? ""}
              placeholder="e.g. 5"
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                setConfig((c) => ({
                  ...c,
                  numPreferences: isNaN(v) ? null : Math.max(1, Math.min(10, v)),
                }));
              }}
              className="w-24 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          {/* Q4: Preference weight slider */}
          <div>
            <p className="text-sm font-medium text-gray-800 mb-2">
              Preference weight
            </p>
            <p className="text-xs text-gray-500 mb-3">
              How much weight to give bigs' preferences vs. littles' preferences.
            </p>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 shrink-0">Favor Littles</span>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(config.bigWeight * 100)}
                onChange={(e) =>
                  setConfig((c) => ({ ...c, bigWeight: parseInt(e.target.value, 10) / 100 }))
                }
                className="flex-1 accent-indigo-600"
              />
              <span className="text-xs text-gray-500 shrink-0">Favor Bigs</span>
            </div>
            <p className="text-xs text-center text-indigo-700 font-medium mt-1">
              {config.bigWeight === 0.5
                ? "Balanced (50/50)"
                : config.bigWeight < 0.5
                ? `${Math.round((1 - config.bigWeight) * 100)}% littles / ${Math.round(config.bigWeight * 100)}% bigs`
                : `${Math.round((1 - config.bigWeight) * 100)}% littles / ${Math.round(config.bigWeight * 100)}% bigs`}
            </p>
          </div>
        </div>

        {!configComplete && (
          <p className="mt-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            Answer all questions above to enable matching.
          </p>
        )}
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
              Littles CSV{littles.length > 0 ? ` (${littles.length} loaded)` : ""}
            </p>
            <CSVUpload label="Drop littles.csv here" onParsed={setLittles} />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">
              Bigs CSV{bigs.length > 0 ? ` (${bigs.length} loaded)` : ""}
            </p>
            <CSVUpload label="Drop bigs.csv here" onParsed={setBigs} />
          </div>
        </div>
      )}

      {/* Editable tables (always shown once data exists, or in manual mode) */}
      {(tab === "manual" || littles.length > 0 || bigs.length > 0) && (
        <div className="flex gap-6 flex-col lg:flex-row mb-6">
          <PersonTable
            title="Littles"
            people={littles}
            otherNames={bigNames}
            onChange={setLittles}
            numPreferences={numPrefs}
          />
          <PersonTable
            title="Bigs"
            people={bigs}
            otherNames={littleNames}
            onChange={setBigs}
            numPreferences={numPrefs}
          />
        </div>
      )}

      {/* Count hint */}
      {(littleCount > 0 || bigCount > 0) && (
        <p className="text-sm text-gray-500 mb-4">
          {littleCount} little{littleCount !== 1 ? "s" : ""} &middot; {bigCount} big{bigCount !== 1 ? "s" : ""}
          {hint.text && (
            <span className={`ml-2 font-medium ${hint.ok ? "text-emerald-600" : "text-amber-600"}`}>
              &middot; {hint.text}
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
                Upload an overrides CSV (columns: <code>Little_1, Little_2, Big_1, Big_2</code> — leave optional columns empty).
                Names will be trimmed and normalized (extra spaces removed, title‑cased).
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
              littleNames={littleNames}
              bigNames={bigNames}
              onChange={setOverrides}
            />
          </div>
        )}
      </div>

      {/* Twin pairs section */}
      <div className="mb-6">
        <button
          onClick={() => setShowTwins((v) => !v)}
          className="flex items-center gap-2 text-sm font-medium text-violet-700 hover:text-violet-900 transition mb-2"
        >
          <span>{showTwins ? "▾" : "▸"}</span>
          Define twin pairs
          {twins.length > 0 && (
            <span className="ml-1 px-2 py-0.5 rounded-full bg-violet-200 text-violet-800 text-xs">
              {twins.length}
            </span>
          )}
        </button>

        {showTwins && (
          <div className="pl-4 border-l-2 border-violet-200">
            <TwinsTable
              twins={twins}
              littleNames={littleNames}
              bigNames={bigNames}
              onChange={setTwins}
            />
          </div>
        )}
      </div>

      {/* Banned pairs section */}
      <div className="mb-6">
        <button
          onClick={() => setShowBanned((v) => !v)}
          className="flex items-center gap-2 text-sm font-medium text-red-700 hover:text-red-900 transition mb-2"
        >
          <span>{showBanned ? "▾" : "▸"}</span>
          Ban specific pairs
          {banned.length > 0 && (
            <span className="ml-1 px-2 py-0.5 rounded-full bg-red-200 text-red-800 text-xs">
              {banned.length}
            </span>
          )}
        </button>

        {showBanned && (
          <div className="pl-4 border-l-2 border-red-200">
            <BannedPairsTable
              banned={banned}
              littleNames={littleNames}
              bigNames={bigNames}
              onChange={setBanned}
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
        disabled={loading || !configComplete}
        className="w-full py-3 rounded-xl bg-indigo-600 text-white font-semibold text-base hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
        title={!configComplete ? "Answer all configuration questions above first" : undefined}
      >
        {loading ? "Running algorithm…" : "Run Matching"}
      </button>
    </div>
  );
}
