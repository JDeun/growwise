import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SystemStatusSection } from "./SystemStatusSection";

const runtime = { started_by_desktop: true };

describe("SystemStatusSection", () => {
  it("offers one-click setup when Ollama is running but models are missing", () => {
    const html = renderToStaticMarkup(
      <SystemStatusSection
        connection={{
          kind: "connected",
          runtime,
          health: {
            status: "ok",
            operation_mode: "core_only",
            core_requires_llm: false,
            llm_configured: true,
            llm_reachable: true,
            llm_model_id: "qwen3.5:4b",
            llm_model_available: false,
            llm_features_enabled: false,
            embedding_reachable: true,
            embedding_model_id: "nomic-embed-text",
            embedding_model_available: false,
            embedding_features_enabled: false,
            vision_reachable: true,
            vision_model_id: "qwen3.5:4b",
            vision_model_available: false,
            vision_features_enabled: false,
            model_provider: "ollama",
          },
        }}
        activeChild={null}
        childrenCount={0}
      />,
    );

    expect(html).toContain("모델 준비 필요");
    expect(html).toContain("기본 AI 준비");
    expect(html).not.toContain("사진 AI 준비");
    expect(html).not.toContain("ollama pull");
  });

  it("shows AI as available only after the text model is actually ready", () => {
    const html = renderToStaticMarkup(
      <SystemStatusSection
        connection={{
          kind: "connected",
          runtime,
          health: {
            status: "ok",
            operation_mode: "ai_enhanced_with_core_fallback",
            core_requires_llm: false,
            llm_configured: true,
            llm_reachable: true,
            llm_model_id: "qwen3.5:4b",
            llm_model_available: true,
            llm_features_enabled: true,
            embedding_reachable: true,
            embedding_model_id: "nomic-embed-text",
            embedding_model_available: true,
            embedding_features_enabled: true,
            vision_reachable: true,
            vision_model_id: "qwen3.5:4b",
            vision_model_available: true,
            vision_features_enabled: true,
            model_provider: "ollama",
          },
        }}
        activeChild={null}
        childrenCount={0}
      />,
    );

    expect(html).toContain("사용 가능");
    expect(html).not.toContain("기본 AI 준비</button>");
  });

  it("does not offer local model download for a reachable remote Ollama endpoint", () => {
    const html = renderToStaticMarkup(
      <SystemStatusSection
        connection={{
          kind: "connected",
          runtime,
          health: {
            status: "ok",
            operation_mode: "ai_enhanced_with_core_fallback",
            core_requires_llm: false,
            llm_configured: true,
            llm_reachable: true,
            llm_model_id: "qwen3.5:9b",
            llm_model_available: null,
            llm_features_enabled: true,
            embedding_reachable: true,
            embedding_model_id: "nomic-embed-text",
            embedding_model_available: true,
            embedding_features_enabled: true,
            vision_reachable: true,
            vision_model_id: "qwen3.5:9b",
            vision_model_available: null,
            vision_features_enabled: true,
            model_provider: "ollama",
          },
        }}
        activeChild={null}
        childrenCount={0}
      />,
    );

    expect(html).toContain("사용 가능");
    expect(html).not.toContain("기본 AI 준비</button>");
    expect(html).not.toContain("사진 AI 준비</button>");
  });

});
