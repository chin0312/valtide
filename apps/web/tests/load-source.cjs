// Load TS/TSX with the project's installed compiler; no extra test framework.
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const ts = require("typescript");
const cache = new Map();
exports.load = function load(filename) {
  filename = path.resolve(__dirname, filename);
  if (cache.has(filename)) return cache.get(filename).exports;
  const module = { exports: {} };
  cache.set(filename, module);
  const source = fs.readFileSync(filename, "utf8").replaceAll("import.meta.env", '({ DEV: false })');
  const { outputText } = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  } });
  const nativeRequire = createRequire(filename);
  const localRequire = (name) => {
    if (name.startsWith(".")) {
      const base = path.resolve(path.dirname(filename), name);
      for (const extension of [".ts", ".tsx"]) if (fs.existsSync(base + extension)) return load(base + extension);
    }
    return nativeRequire(name);
  };
  new Function("require", "module", "exports", outputText)(localRequire, module, module.exports);
  return module.exports;
};
