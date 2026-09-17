import {
  createActivity,
  listMaterialResults,
  type ActivityPlan,
  type GeneratedMaterial,
  type MaterialUseHistoryItem,
} from "./api";

type MaterialQuestSource = Pick<GeneratedMaterial, "id" | "child_id" | "title">;

interface MaterialQuestApi {
  listResults: (materialId: string) => Promise<MaterialUseHistoryItem[]>;
  create: (childId: string, title: string, sourceRefs: string[]) => Promise<ActivityPlan>;
}

export interface EnsuredMaterialQuest {
  item: MaterialUseHistoryItem;
  created: boolean;
}

const DEFAULT_API: MaterialQuestApi = {
  listResults: listMaterialResults,
  create: createActivity,
};

const pendingEnsures = new Map<string, Promise<EnsuredMaterialQuest>>();

/**
 * Ensure one approved GeneratedMaterial has a real ActivityPlan behind its quest UI.
 *
 * The material card used to display a synthetic "생성됨" state until the parent pressed Start or
 * saved a result. That meant the global Quest Board could not see freshly approved material. This
 * helper closes that gap and also coalesces concurrent React calls so one material is not registered
 * twice inside a single desktop process.
 */
export function ensureMaterialQuest(
  material: MaterialQuestSource,
  api: MaterialQuestApi = DEFAULT_API,
): Promise<EnsuredMaterialQuest> {
  const existing = pendingEnsures.get(material.id);
  if (existing) return existing;

  const pending = (async () => {
    const history = await api.listResults(material.id);
    if (history[0]) return { item: history[0], created: false };

    const activity = await api.create(
      material.child_id,
      material.title,
      [`material:${material.id}`],
    );
    const refreshed = await api.listResults(material.id);
    return {
      item: refreshed[0] ?? { activity, learning_logs: [] },
      created: true,
    };
  })().finally(() => {
    pendingEnsures.delete(material.id);
  });

  pendingEnsures.set(material.id, pending);
  return pending;
}
