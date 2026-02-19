export interface Person {
  name: string;
  preferences: string[]; // up to 5 sophomore/freshman names in ranked order
}

export interface Match {
  freshman: string;
  big_1: string;
  big_2: string | null;
  trio: boolean;
}

export interface SatisfactionRow {
  freshman: string;
  big_1: string;
  big_2: string | null;
  freshman_score: number;
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
