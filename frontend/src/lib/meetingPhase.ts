export type MeetingPhase = "exploration" | "synthesis" | "output";

export function getMeetingPhase(round: number, maxRounds: number): MeetingPhase {
  if (maxRounds <= 1) return "output";
  if (round === 1) return "exploration";
  if (round >= maxRounds) return "output";
  return "synthesis";
}

export function getPhaseLabel(
  phase: MeetingPhase,
  t: (key: string) => string
): string {
  switch (phase) {
    case "exploration":
      return t("phaseExploration");
    case "synthesis":
      return t("phaseSynthesis");
    case "output":
      return t("phaseOutput");
  }
}
