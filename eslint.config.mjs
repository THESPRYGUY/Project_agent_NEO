import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    files: ["src/ui/**/*.js"],
    languageOptions: {
      sourceType: "module",
      ecmaVersion: 2021
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
