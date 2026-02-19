import { useState } from "react";
import type { MatchResult } from "./types";
import InputPage from "./components/InputPage";
import ResultsPage from "./components/ResultsPage";

export default function App() {
  const [result, setResult] = useState<MatchResult | null>(null);

  if (result) {
    return <ResultsPage result={result} onBack={() => setResult(null)} />;
  }

  return <InputPage onResult={setResult} />;
}
