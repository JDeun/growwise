import type { FormEvent } from "react";
import { useCallback, useState } from "react";

import {
  editMaterial,
  generateMaterial,
  reviewMaterial,
  reviseMaterial,
  type MaterialKind,
  type MaterialStatus,
} from "./api";
import { errorMessage } from "./child-context-state";

type MaterialManagementOptions = {
  childId: string | null;
  getRequestId: () => number;
  scopeIsCurrent: (childId: string, requestId: number) => boolean;
  reloadMaterials: () => Promise<void>;
  announceWrite: (message: string) => void;
};

export function useMaterialManagement({
  childId,
  getRequestId,
  scopeIsCurrent,
  reloadMaterials,
  announceWrite,
}: MaterialManagementOptions) {
  const [materialKind, setMaterialKind] = useState<MaterialKind>("activity_guide");
  const [materialTopic, setMaterialTopic] = useState("");
  const [materialGoal, setMaterialGoal] = useState("");
  const [selectedResourceRefs, setSelectedResourceRefs] = useState<string[]>([]);
  const [materialBusy, setMaterialBusy] = useState(false);
  const [materialError, setMaterialError] = useState<string | null>(null);
  const [revisionNotes, setRevisionNotes] = useState<Record<string, string>>({});
  const [editingMaterialId, setEditingMaterialId] = useState<string | null>(null);

  const resetMaterialState = useCallback(() => {
    setMaterialTopic("");
    setMaterialGoal("");
    setSelectedResourceRefs([]);
    setMaterialBusy(false);
    setMaterialError(null);
    setRevisionNotes({});
    setEditingMaterialId(null);
  }, []);

  function currentScope(): { childId: string; requestId: number } | null {
    if (!childId) return null;
    return { childId, requestId: getRequestId() };
  }

  async function handleGenerateMaterial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const scope = currentScope();
    if (!scope) return;
    const topic = materialTopic.trim();
    if (!topic) {
      setMaterialError("자료 주제를 입력해 주세요.");
      return;
    }
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await generateMaterial(
        scope.childId,
        materialKind,
        topic,
        materialGoal.trim() || undefined,
        selectedResourceRefs,
      );
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      setMaterialTopic("");
      setMaterialGoal("");
      setSelectedResourceRefs([]);
      await reloadMaterials();
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        announceWrite("학습 자료 초안을 생성했습니다.");
      }
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setMaterialError(errorMessage(error, "자료 생성에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setMaterialBusy(false);
    }
  }

  async function handleReviewMaterial(materialId: string, status: MaterialStatus) {
    const scope = currentScope();
    if (!scope) return;
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await reviewMaterial(materialId, status);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      await reloadMaterials();
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      announceWrite(
        status === "approved"
          ? "학습 자료를 승인했습니다."
          : status === "rejected"
            ? "학습 자료를 반려했습니다."
            : "자료 검토 상태를 변경했습니다.",
      );
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setMaterialError(errorMessage(error, "자료 검토 상태 변경에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setMaterialBusy(false);
    }
  }

  async function handleReviseMaterial(materialId: string) {
    const scope = currentScope();
    if (!scope) return;
    const note = (revisionNotes[materialId] ?? "").trim();
    if (!note) {
      setMaterialError("수정할 내용을 짧게 적어 주세요.");
      return;
    }
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await reviseMaterial(materialId, note);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      await reloadMaterials();
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      setRevisionNotes((current) => {
        const next = { ...current };
        delete next[materialId];
        return next;
      });
      announceWrite("수정본을 생성했습니다.");
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setMaterialError(errorMessage(error, "수정본 생성에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setMaterialBusy(false);
    }
  }

  async function handleParentEdit(
    materialId: string,
    title: string,
    contentMarkdown: string,
    note: string | null,
  ) {
    const scope = currentScope();
    if (!scope) return;
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await editMaterial(materialId, title, contentMarkdown, note);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      await reloadMaterials();
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      setEditingMaterialId(null);
      announceWrite("편집본을 저장했습니다.");
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setMaterialError(errorMessage(error, "편집본 저장에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setMaterialBusy(false);
    }
  }

  function toggleResourceRef(resourceId: string) {
    const ref = `resource:${resourceId}`;
    setSelectedResourceRefs((current) =>
      current.includes(ref) ? current.filter((item) => item !== ref) : [...current, ref],
    );
  }

  return {
    materialKind,
    materialTopic,
    materialGoal,
    selectedResourceRefs,
    materialBusy,
    materialError,
    revisionNotes,
    editingMaterialId,
    setMaterialKind,
    setMaterialTopic,
    setMaterialGoal,
    toggleResourceRef,
    setRevisionNote: (materialId: string, note: string) =>
      setRevisionNotes((current) => ({ ...current, [materialId]: note })),
    setEditingMaterialId,
    handleGenerateMaterial,
    handleReviewMaterial,
    handleReviseMaterial,
    handleParentEdit,
    resetMaterialState,
  };
}
