// CSV text for downloads. It has no imports on purpose, so Node's test runner can load it directly.

// A cell starting with one of these characters can run as a formula when the file is opened in Excel,
// Google Sheets or LibreOffice (CSV injection). A leading apostrophe makes the spreadsheet show it as text.
const FORMULA_START = /^[=+\-@\t\r]/;

// A number written as text ("-5", "+3.2") is harmless, and should stay a number in the spreadsheet.
const PLAIN_NUMBER = /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i;

export function neutralizeFormula(text: string): string {
  return FORMULA_START.test(text) && !PLAIN_NUMBER.test(text) ? `'${text}` : text;
}

/** One CSV cell. Numbers and booleans are written as they are. Text is made safe and quoted when needed. */
export function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = typeof value === "string" ? neutralizeFormula(value) : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(columns: string[], rows: Record<string, unknown>[]): string {
  const header = columns.map(escapeCsvCell).join(",");
  const body = rows.map((row) => columns.map((column) => escapeCsvCell(row[column])).join(","));
  return [header, ...body].join("\n");
}
