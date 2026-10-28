// Run with: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { escapeCsvCell, neutralizeFormula, toCsv } from "./csv.ts";

test("text that could run as a formula gets a leading apostrophe", () => {
  assert.equal(neutralizeFormula("=1+1"), "'=1+1");
  assert.equal(neutralizeFormula("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0");
  assert.equal(neutralizeFormula("-2+3"), "'-2+3");
  assert.equal(neutralizeFormula("@SUM(A1:A9)"), "'@SUM(A1:A9)");
  assert.equal(neutralizeFormula("\t=1"), "'\t=1");
  assert.equal(neutralizeFormula("-"), "'-");
});

test("ordinary text and numbers written as text are left alone", () => {
  for (const text of ["S1000", "hello world", "a=b", "x-1", "-5", "+3.2", "-.5", "10", "-1e-3"]) {
    assert.equal(neutralizeFormula(text), text, text);
  }
});

test("numbers, booleans and empty values are written as they are", () => {
  assert.equal(escapeCsvCell(-5), "-5");
  assert.equal(escapeCsvCell(12.5), "12.5");
  assert.equal(escapeCsvCell(true), "true");
  assert.equal(escapeCsvCell(null), "");
  assert.equal(escapeCsvCell(undefined), "");
});

test("cells with commas, quotes or line breaks are quoted", () => {
  assert.equal(escapeCsvCell("a,b"), '"a,b"');
  assert.equal(escapeCsvCell('say "hi"'), '"say ""hi"""');
  assert.equal(escapeCsvCell("line1\nline2"), '"line1\nline2"');
});

test("a dangerous cell is both neutralized and quoted when needed", () => {
  assert.equal(escapeCsvCell("=HYPERLINK(\"http://x\",\"y\")"), '"\'=HYPERLINK(""http://x"",""y"")"');
  assert.equal(escapeCsvCell("\r=1"), '"\'\r=1"');
});

test("toCsv writes the header row, neutralizes header cells too, and fills missing cells", () => {
  const csv = toCsv(["=evil", "ok", "gone"], [{ "=evil": "x", ok: 1 }, { "=evil": "=1+1", ok: null }]);
  assert.equal(csv, "'=evil,ok,gone\nx,1,\n'=1+1,,");
});

test("toCsv with no rows is just the header", () => {
  assert.equal(toCsv(["a", "b"], []), "a,b");
});
