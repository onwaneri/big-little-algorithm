import axios from "axios";
import type { MatchResult, OverrideMatch, Person, TwinPair, BannedPair } from "./types";

// In production the frontend is served by FastAPI on the same domain,
// so relative URLs work. In local dev, Vite proxies /api/* to :8000.
const BASE = "";

export async function runMatch(
  freshmen: Person[],
  sophomores: Person[],
  overrides: OverrideMatch[] = [],
  twins: TwinPair[] = [],
  banned: BannedPair[] = []
): Promise<MatchResult> {
  const { data } = await axios.post<MatchResult>(`${BASE}/api/match`, {
    freshmen,
    sophomores,
    overrides,
    twins,
    banned,
  });
  return data;
}

export async function parseCSV(file: File): Promise<Person[]> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await axios.post<Person[]>(`${BASE}/api/parse-csv`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function parseOverridesCSV(file: File): Promise<OverrideMatch[]> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await axios.post<OverrideMatch[]>(
    `${BASE}/api/parse-overrides-csv`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}
