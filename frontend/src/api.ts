import axios from "axios";
import type { MatchResult, Person } from "./types";

const BASE = "http://localhost:8000";

export async function runMatch(
  freshmen: Person[],
  sophomores: Person[]
): Promise<MatchResult> {
  const { data } = await axios.post<MatchResult>(`${BASE}/api/match`, {
    freshmen,
    sophomores,
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
