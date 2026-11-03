import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { describe, expect, it } from "vitest";

describe("Desktop IPC wiring", () => {
  it("registers every literal command used by frontend API calls", () => {
    const sourceRoot = fileURLToPath(new URL(".", import.meta.url));
    const rust = readFileSync(resolve(sourceRoot, "../src-tauri/src/lib.rs"), "utf8");
    const handlers = /tauri::generate_handler!\[([\s\S]*?)\]/.exec(rust)?.[1];
    expect(handlers).toBeDefined();
    const registered = new Set(handlers?.match(/\b[a-z][a-z_]+\b/g));
    const missing: string[] = [];
    let checked = 0;

    for (const file of readdirSync(sourceRoot, { recursive: true, encoding: "utf8" })) {
      if (typeof file !== "string" || !/\.(ts|tsx)$/.test(file) || /\.test\./.test(file)) continue;
      const parsed = ts.createSourceFile(file, readFileSync(resolve(sourceRoot, file), "utf8"),
        ts.ScriptTarget.Latest, true);
      function visit(node: ts.Node) {
        if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)
          && ["invoke", "call", "callStudy"].includes(node.expression.text)) {
          const command = node.arguments[0];
          if (command && ts.isStringLiteral(command)) {
            checked += 1;
            if (!registered.has(command.text)) missing.push(`${file}: ${command.text}`);
          }
        }
        ts.forEachChild(node, visit);
      }
      visit(parsed);
    }

    expect(checked).toBeGreaterThan(50);
    expect(missing).toEqual([]);
  });
});
