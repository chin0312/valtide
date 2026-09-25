import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import typescript from "typescript";

const playbackSource = await readFile(new URL("../src/lib/playback.ts", import.meta.url), "utf8");
const playbackModule = await import(
  `data:text/javascript,${encodeURIComponent(
    typescript.transpileModule(playbackSource, {
      compilerOptions: {
        module: typescript.ModuleKind.ESNext,
        target: typescript.ScriptTarget.ES2022,
      },
    }).outputText,
  )}`,
);
const { advancePosition, clampPosition } = playbackModule;

test("an earlier first-frame timestamp cannot select observation -1", () => {
  assert.equal(advancePosition(0, -8, 26), 0);
});

test("playback moves continuously and stops exactly at the last observation", () => {
  assert.equal(advancePosition(0, 60, 26), 0.5);
  assert.equal(advancePosition(12.5, 120, 26), 13.5);
  assert.equal(advancePosition(24.9, 120, 26), 25);
});

test("stale and invalid positions stay within the current sequence", () => {
  for (const position of [-1, NaN, Infinity]) assert.equal(clampPosition(position, 26), 0);
  assert.equal(clampPosition(25, 6), 5);
  assert.equal(clampPosition(0, 0), 0);
});
