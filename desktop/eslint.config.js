import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

// shortcut: override vulnerable minimatch 10 until ESLint and TypeScript ESLint require 11.0.1+.
export default tseslint.config(
  {
    ignores: ["dist/**", "src-tauri/**"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}", "vite.config.ts"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
);
