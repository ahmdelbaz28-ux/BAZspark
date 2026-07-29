// @ts-check
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";
import globals from "globals";

export default tseslint.config(
	{ ignores: ["dist/", "electron/compiled/", "node_modules/", "scripts/"] },
	{
		languageOptions: {
			globals: {
				...globals.browser,
				...globals.node,
			},
		},
	},
	js.configs.recommended,
	...tseslint.configs.recommended,
	{
		plugins: { "react-hooks": reactHooks },
		rules: {
			...reactHooks.configs.recommended.rules,
			"no-empty": ["error", { allowEmptyCatch: true }],
			"@typescript-eslint/no-unused-vars": [
				"warn",
				{
					argsIgnorePattern: "^_",
					varsIgnorePattern: "^_",
					caughtErrors: "none",
				},
			],
			"@typescript-eslint/no-explicit-any": "warn",
		},
	},
	// Playwright test setup files — not React components, so disable React hooks rules
	// Must come AFTER the react-hooks config to take precedence in flat config
	{
		files: ["tests/setup/**"],
		rules: {
			"react-hooks/rules-of-hooks": "off",
		},
	},
);
