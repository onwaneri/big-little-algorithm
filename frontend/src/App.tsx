import { useState } from "react";
import type { MatchConfig, MatchResult, Person, OverrideMatch, TwinPair, BannedPair } from "./types";
import InputPage from "./components/InputPage";
import ResultsPage from "./components/ResultsPage";

interface InputState {
  littles: Person[];
  bigs: Person[];
  overrides: OverrideMatch[];
  twins: TwinPair[];
  banned: BannedPair[];
  config: MatchConfig;
}

const DEFAULT_CONFIG: MatchConfig = {
  everyBigNeedsLittle: null,
  everyLittleNeedsBig: null,
  numPreferences: null,
  bigWeight: 0.5,
};

export default function App() {
  const [result, setResult] = useState<MatchResult | null>(null);
  const [inputState, setInputState] = useState<InputState>({
    littles: [],
    bigs: [],
    overrides: [],
    twins: [],
    banned: [],
    config: DEFAULT_CONFIG,
  });

  function handleResult(
    result: MatchResult,
    littles: Person[],
    bigs: Person[],
    overrides: OverrideMatch[] = [],
    twins: TwinPair[] = [],
    banned: BannedPair[] = [],
    config: MatchConfig = DEFAULT_CONFIG
  ) {
    setResult(result);
    setInputState({ littles, bigs, overrides, twins, banned, config });
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
      initialLittles={inputState.littles}
      initialBigs={inputState.bigs}
      initialOverrides={inputState.overrides}
      initialTwins={inputState.twins}
      initialBanned={inputState.banned}
      initialConfig={inputState.config}
    />
  );
}
