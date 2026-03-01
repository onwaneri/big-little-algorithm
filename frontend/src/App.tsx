import { useState } from "react";
import type { MatchResult, Person, OverrideMatch, TwinPair, BannedPair } from "./types";
import InputPage from "./components/InputPage";
import ResultsPage from "./components/ResultsPage";

interface InputState {
  freshmen: Person[];
  sophomores: Person[];
  overrides: OverrideMatch[];
  twins: TwinPair[];
  banned: BannedPair[];
}

export default function App() {
  const [result, setResult] = useState<MatchResult | null>(null);
  const [inputState, setInputState] = useState<InputState>({
    freshmen: [],
    sophomores: [],
    overrides: [],
    twins: [],
    banned: [],
  });

  function handleResult(
    result: MatchResult,
    fresh: Person[],
    soph: Person[],
    overrides: OverrideMatch[] = [],
    twins: TwinPair[] = [],
    banned: BannedPair[] = []
  ) {
    setResult(result);
    setInputState({ freshmen: fresh, sophomores: soph, overrides, twins, banned });
  }

  function handleEditConstraints() {
    setResult(null);
  }

  if (result) {
    return (
      <ResultsPage
        result={result}
        onEditConstraints={handleEditConstraints}
      />
    );
  }

  return (
    <InputPage
      onResult={handleResult}
      initialOverrides={inputState.overrides}
      initialTwins={inputState.twins}
      initialBanned={inputState.banned}
    />
  );
}
