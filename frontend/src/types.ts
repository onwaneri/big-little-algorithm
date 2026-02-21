export interface Person {
  name: string;
  preferences: string[]; // up to 5 names in ranked order
}

export interface OverrideMatch {
  freshman_1: string;
  freshman_2: string | null;  // populated for 2-little trios
  big_1: string;
  big_2: string | null;       // populated for 2-big trios
}

export interface Match {
  freshman: string;
  freshman_2: string | null;  // populated for 2-little trios
  big_1: string;
  big_2: string | null;       // populated for 2-big trios
  trio: boolean;
}

export interface SatisfactionRow {
  freshman: string;
  freshman_2: string | null;
  big_1: string;
  big_2: string | null;
  freshman_score: number;
  freshman_2_score: number | null;
  big_1_score: number;
  big_2_score: number | null;
  pair_score: number;
}

export interface Summary {
  median_pair_score: number;
  average_pair_score: number;
  mutual_count: number;
}

export interface MatchResult {
  matches: Match[];
  satisfaction: SatisfactionRow[];
  summary: Summary;
}
