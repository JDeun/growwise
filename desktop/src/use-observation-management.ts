import type { FormEvent } from "react";
import { useCallback, useState } from "react";

import { createObservation, type ExperienceAxis } from "./api";
import { errorMessage } from "./child-context-state";

type ObservationManagementOptions = {
  childId: string | null;
  getRequestId: () => number;
  scopeIsCurrent: (childId: string, requestId: number) => boolean;
  clearActivities: () => void;
  clearSearchResult: () => void;
  reloadGrowth: () => Promise<void>;
  reloadObservations: () => Promise<void>;
  announceWrite: (message: string) => void;
};

export function useObservationManagement({
  childId,
  getRequestId,
  scopeIsCurrent,
  clearActivities,
  clearSearchResult,
  reloadGrowth,
  reloadObservations,
  announceWrite,
}: ObservationManagementOptions) {
  const [observation, setObservation] = useState("");
  const [selectedAxes, setSelectedAxes] = useState<ExperienceAxis[]>([]);
  const [selectedActivityId, setSelectedActivityId] = useState("");
  const [observationSaving, setObservationSaving] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);

  const resetObservationState = useCallback(() => {
    setObservation("");
    setSelectedAxes([]);
    setSelectedActivityId("");
    setObservationSaving(false);
    setObservationError(null);
  }, []);

  async function handleCreateObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!childId) return;
    const requestId = getRequestId();
    const text = observation.trim();
    if (!text) {
      setObservationError("기억할 가치가 있는 관찰을 짧게 적어 주세요.");
      return;
    }
    setObservationSaving(true);
    setObservationError(null);
    try {
      await createObservation({
        child_id: childId,
        observation: text,
        experience_axes: selectedAxes,
        activity_plan_id: selectedActivityId || null,
      });
      if (!scopeIsCurrent(childId, requestId)) return;
      setObservation("");
      setSelectedAxes([]);
      setSelectedActivityId("");
      clearActivities();
      clearSearchResult();
      await Promise.all([reloadGrowth(), reloadObservations()]);
      if (scopeIsCurrent(childId, requestId)) {
        announceWrite("관찰 기록을 저장했습니다.");
      }
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setObservationError(errorMessage(error, "관찰 기록 저장에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setObservationSaving(false);
    }
  }

  return {
    observation,
    selectedAxes,
    selectedActivityId,
    observationSaving,
    observationError,
    setObservation,
    setSelectedAxes,
    setSelectedActivityId,
    handleCreateObservation,
    resetObservationState,
  };
}
