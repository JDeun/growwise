import type { FormEvent } from "react";
import { useCallback, useState } from "react";

import {
  editMaterial,
  generateMaterial,
  reviewMaterial,
  reviseMaterial,
  useMaterial,
  type MaterialKind,
  type MaterialStatus,
} from "./api";
import { errorMessage } from "./child-context-state";
import { materialAiPending } from "./material-ai-polling";
import { retryMaterialEnhancement } from "./record-actions-api";

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
      const material = await generateMaterial(
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
        announceWrite(materialAiPending(material)
          ? "기본 초안을 저장했습니다. AI 자료는 백그라운드에서 작성·검토하며 준비되면 알려드립니다."
          : "학습 자료 초안을 생성했습니다.");
      }
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setMaterialError(errorMessage(error, "자료 생성에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setMaterialBusy(false);
    }
  }

  async function handleUseMaterial(materialId: string) {
    const scope = currentScope();
    if (!scope) return;
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await useMaterial(materialId);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      await reloadMaterials();
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      announceWrite("활동을 사용할 준비가 됐습니다.");
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setMaterialError(errorMessage(error, "활동 사용 준비에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setMaterialBusy(false);
    }
  }

  async function handleRetryMaterial(materialId: string) {
    const scope = currentScope();
    if (!scope) return;
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await retryMaterialEnhancement(materialId);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      await reloadMaterials();
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        announceWrite("AI 보강을 다시 시작했습니다. 자료가 준비되면 알려드립니다.");
      }
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setMaterialError(errorMessage(error, "AI 보강을 다시 시작하지 못했습니다. 설정에서 AI 상태를 확인해 주세요."));
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
      const material = await reviseMaterial(materialId, note);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      await reloadMaterials();
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      setRevisionNotes((current) => {
        const next = { ...current };
        delete next[materialId];
        return next;
      });
      announceWrite(materialAiPending(material)
        ? "수정 초안을 저장했습니다. AI 수정본은 준비되면 알려드립니다."
        : "수정본을 생성했습니다.");
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

  function removeResourceRef(resourceId: string) {
    const ref = `resource:${resourceId}`;
    setSelectedResourceRefs((current) => current.filter((item) => item !== ref));
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
    removeResourceRef,
    setRevisionNote: (materialId: string, note: string) =>
      setRevisionNotes((current) => ({ ...current, [materialId]: note })),
    setEditingMaterialId,
    handleGenerateMaterial,
    handleUseMaterial,
    handleRetryMaterial,
    handleReviewMaterial,
    handleReviseMaterial,
    handleParentEdit,
    resetMaterialState,
  };
}
