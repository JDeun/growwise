import type { FormEvent } from "react";
import { useCallback, useState } from "react";

import {
  createResource,
  deleteResource,
  updateResource,
  type ChildProfile,
  type ResourceCreateInput,
  type ResourceKind,
  type ResourceRecord,
} from "./api";
import { errorMessage } from "./child-context-state";
import { emptyResourceDetails, resourceDetailsPayload } from "./resource-details";

type ResourceManagementOptions = {
  child: Pick<ChildProfile, "id" | "stage"> | null;
  getRequestId: () => number;
  scopeIsCurrent: (childId: string, requestId: number) => boolean;
  reloadLibrary: () => Promise<void>;
  replaceResource: (resource: ResourceRecord) => void;
  removeResource: (resourceId: string) => void;
  removeResourceRef: (resourceId: string) => void;
  announceWrite: (message: string) => void;
};

export function useResourceManagement({
  child,
  getRequestId,
  scopeIsCurrent,
  reloadLibrary,
  replaceResource,
  removeResource,
  removeResourceRef,
  announceWrite,
}: ResourceManagementOptions) {
  const [resourceKind, setResourceKind] = useState<ResourceKind>("note");
  const [resourceTitle, setResourceTitle] = useState("");
  const [resourceContent, setResourceContent] = useState("");
  const [resourceDetails, setResourceDetails] = useState(emptyResourceDetails);
  const [resourceSaving, setResourceSaving] = useState(false);
  const [resourceError, setResourceError] = useState<string | null>(null);

  const resetResourceState = useCallback(() => {
    setResourceTitle("");
    setResourceContent("");
    setResourceDetails(emptyResourceDetails());
    setResourceSaving(false);
    setResourceError(null);
  }, []);

  function currentScope(): { childId: string; requestId: number } | null {
    if (!child) return null;
    return { childId: child.id, requestId: getRequestId() };
  }

  async function handleCreateResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const scope = currentScope();
    if (!scope || !child) return;
    const title = resourceTitle.trim();
    const content = resourceContent.trim();
    if (!title) {
      setResourceError("자료 제목을 입력해 주세요.");
      return;
    }
    setResourceSaving(true);
    setResourceError(null);
    try {
      await createResource({
        kind: resourceKind,
        title,
        ...resourceDetailsPayload(resourceDetails, scope.childId),
        content: content || null,
        stage_tags: [child.stage],
        provenance: { origin: "desktop_manual" },
      });
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      setResourceTitle("");
      setResourceContent("");
      setResourceDetails(emptyResourceDetails());
      await reloadLibrary();
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        announceWrite("자료를 저장했습니다.");
      }
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setResourceError(errorMessage(error, "자료 저장에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setResourceSaving(false);
    }
  }

  async function handleUpdateResource(resourceId: string, request: ResourceCreateInput) {
    const scope = currentScope();
    if (!scope) return;
    setResourceSaving(true);
    setResourceError(null);
    try {
      const updated = await updateResource(resourceId, request, scope.childId);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      replaceResource(updated);
      await reloadLibrary();
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      announceWrite("자료를 수정했습니다.");
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setResourceError(errorMessage(error, "자료 수정에 실패했습니다."));
      }
      throw error;
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setResourceSaving(false);
    }
  }

  async function handleDeleteResource(resourceId: string) {
    const scope = currentScope();
    if (!scope) return;
    setResourceSaving(true);
    setResourceError(null);
    try {
      await deleteResource(resourceId, scope.childId);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      removeResource(resourceId);
      removeResourceRef(resourceId);
      announceWrite("자료를 삭제했습니다.");
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setResourceError(errorMessage(error, "자료 삭제에 실패했습니다."));
      }
      throw error;
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setResourceSaving(false);
    }
  }

  return {
    resourceKind,
    resourceTitle,
    resourceContent,
    resourceDetails,
    resourceSaving,
    resourceError,
    setResourceKind,
    setResourceTitle,
    setResourceContent,
    setResourceDetails,
    handleCreateResource,
    handleUpdateResource,
    handleDeleteResource,
    resetResourceState,
  };
}
