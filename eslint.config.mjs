import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    files: ["src/ui/**/*.js"],
    languageOptions: {
      sourceType: "module",
      ecmaVersion: 2021,
      globals: {
        window: "readonly",
        document: "readonly",
        fetch: "readonly",
        console: "readonly"
      }
    },
    rules: {
      "no-unused-vars": [
        "error",
        {
          "args": "none",
          "varsIgnorePattern": "^_"
        }
      ],
      "no-console": "off"
    }
  }
];
