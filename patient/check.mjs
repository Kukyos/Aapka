// One runnable check for the client-side logic that can actually be wrong.
//
//   node check.mjs
//
// Node 22.6+ strips TypeScript types on import, so this runs the real function from
// speech.ts rather than a copy of it — a check that reimplements what it is checking
// checks nothing.
//
// Only the language heuristic is here. Barge-in needs a microphone and a room, and the
// QR needs a phone; both are covered by the server-side test and by standing in front
// of the terminal. This covers the one piece that is pure, decidable, and silently
// wrong if the Devanagari range is off by a character.

import assert from "node:assert/strict";
import { detectLanguage } from "./src/speech.ts";

const cases = [
  ["मुझे पेट में दर्द है", "hi"],
  ["my stomach hurts", "en"],
  ["हिंदी", "hi"],
  ["English", "en"],
  // Code-switching is the normal case in an Indian OPD, not the edge case. The script
  // carrying the sentence wins over the loanwords sitting inside it.
  ["मुझे fever है", "hi"],
  ["BP sugar problem", "en"],
  // Not enough to decide. Every one of these must leave the screen untouched rather
  // than guess — a wrong pre-selection is recoverable, a confident one is annoying.
  ["", null],
  ["हाँ", null],
  ["ok", null],
  ["...", null],
];

for (const [text, expected] of cases) {
  assert.equal(detectLanguage(text), expected, `detectLanguage(${JSON.stringify(text)})`);
}
console.log(`language heuristic: ${cases.length} cases pass`);
