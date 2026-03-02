export interface Person {
  name: string;
  preferences: string[];
}

export interface MatchConfig {
  everyBigNeedsLittle: boolean | null;   // null = unanswered
  everyLittleNeedsBig: boolean | null;   // null = unanswered
  numPreferences: number | null;          // null = unanswered
  bigWeight: number;                      // 0 = favor littles, 1 = favor bigs (default 0.5)
}

export interface TwinPair {
  person_1: string;
  person_2: string;
  group: "big" | "little";
}

export interface BannedPair {
  little: string;
  big: string;
}

export interface OverrideMatch {
  little_1: string;
  little_2: string | null;  // populated for 2-little trios
  big_1: string;
  big_2: string | null;     // populated for 2-big trios
}

export interface Match {
  little: string;
  little_2: string | null;  // populated for 2-little trios
  big_1: string;
  big_2: string | null;     // populated for 2-big trios
  trio: boolean;
}

export interface SatisfactionRow {
  little: string;
  little_2: string | null;
  big_1: string;
  big_2: string | null;
  little_score: number | null;
  little_2_score: number | null;
  big_1_score: number | null;
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
  unmatched_bigs: string[];
  unmatched_littles: string[];
}
