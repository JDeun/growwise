import type { FormEvent } from "react";

import type { GeneratedMaterial, MaterialKind, MaterialStatus, ResourceRecord, Stage } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

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
}

export function MaterialWorkspaceIntegration({ controller }: { controller: MaterialWorkspaceController }) {
  return (
    <MaterialWorkspace
      materials={controller.materials}
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
    />
  );
}
