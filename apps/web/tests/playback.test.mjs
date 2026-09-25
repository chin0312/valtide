import assert from "node:assert/strict";
import test from "node:test";
import { advancePosition, clampPosition } from "../src/lib/playback.ts";

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
