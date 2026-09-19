import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  listMaterials,
  type GeneratedMaterial,
  type MaterialKind,
  type MaterialStatus,
  type ResourceRecord,
  type Stage,
} from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const MATERIAL_AI_POLL_INTERVAL_MS = 1500;

export interface MaterialWorkspaceController {
  materials: GeneratedMaterial[];
  resources: ResourceRecord[];
  stage?: Stage;
  materialKind: MaterialKind;
  materialTopic: string;
  materialGoal: string;
  selectedResourceRefs: string[];
  materialBusy: boolean;
  materialError: string | null;
  revisionNotes: Record<string, string>;
  editingMaterialId: string | null;
  setMaterialKind: (kind: MaterialKind) => void;
  setMaterialTopic: (value: string) => void;
  setMaterialGoal: (value: string) => void;
  toggleResourceRef: (resourceId: string) => void;
  handleGenerateMaterial: (event: FormEvent<HTMLFormElement>) => void;
  handleReviewMaterial: (materialId: string, status: MaterialStatus) => void;
  setRevisionNote: (materialId: string, note: string) => void;
  handleReviseMaterial: (materialId: string) => void;
  setEditingMaterialId: (materialId: string | null) => void;
  handleParentEdit: (materialId: string, title: string, content: string, note: string | null) => void;
  handlePrintMaterial: (material: GeneratedMaterial) => void;
  handleMaterialResultRecorded?: () => void | Promise<void>;
}

export function MaterialWorkspaceIntegration({ controller }: { controller: MaterialWorkspaceController }) {
  const [displayMaterials, setDisplayMaterials] = useState(controller.materials);
  const refreshAfterResult = controller.handleMaterialResultRecorded ?? (() => undefined);

  useEffect(() => {
    setDisplayMaterials(controller.materials);
  }, [controller.materials]);

  const pendingChildIds = useMemo(
    () => [
      ...new Set(
        displayMaterials
          .filter((material) => material.ai_status === "queued" || material.ai_status === "running")
          .map((material) => material.child_id),
      ),
    ],
    [displayMaterials],
  );

  useEffect(() => {
    if (pendingChildIds.length === 0) return;
    let cancelled = false;

    const poll = () => {
      void Promise.all(pendingChildIds.map((childId) => listMaterials(childId)))
        .then((groups) => {
          if (cancelled) return;
          const refreshed = new Map(
            groups.flat().map((material) => [material.id, material] as const),
          );
          setDisplayMaterials((current) =>
            current.map((material) => refreshed.get(material.id) ?? material),
          );
        })
        .catch(() => undefined);
    };

    const timer = window.setInterval(poll, MATERIAL_AI_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [pendingChildIds]);

  return (
    <MaterialWorkspace
      materials={displayMaterials}
      resources={controller.resources}
      stage={controller.stage}
      materialKind={controller.materialKind}
      topic={controller.materialTopic}
      goal={controller.materialGoal}
      selectedResourceRefs={controller.selectedResourceRefs}
      busy={controller.materialBusy}
      error={controller.materialError}
      revisionNotes={controller.revisionNotes}
      editingMaterialId={controller.editingMaterialId}
      onKindChange={controller.setMaterialKind}
      onTopicChange={controller.setMaterialTopic}
      onGoalChange={controller.setMaterialGoal}
      onToggleResource={controller.toggleResourceRef}
      onGenerate={controller.handleGenerateMaterial}
      onReview={controller.handleReviewMaterial}
      onRevisionNoteChange={controller.setRevisionNote}
      onRevise={controller.handleReviseMaterial}
      onEditStart={controller.setEditingMaterialId}
      onEdit={controller.handleParentEdit}
      onPrint={controller.handlePrintMaterial}
      onResultRecorded={refreshAfterResult}
    />
  );
}
