// Syntax colouring for the page's editors: the same lexer as tools/highlight.py, which colours
// the book's listings at build time, so code looks the same before and after Edit and run.
// tests/test_site.py holds the two to the same output on every listing the book quotes.
//
// A textarea cannot colour its own text, so an editor is two layers in one box: the colours drawn
// in a <pre> behind, and the textarea in front with its text transparent and its caret showing.
// Every keystroke redraws the layer behind, and scrolling one scrolls the other.

const PY_KEYWORDS = "and as assert async await break class continue def del elif else except False finally for "
  + "from global if import in is lambda None nonlocal not or pass raise return True try while with yield";
const SQL_KEYWORDS = "select from where group by order having count sum min max avg and or not as limit join on "
  + "inner left right outer distinct asc desc between in is null";
const NUMBER = String.raw`\b(?:0x[0-9a-fA-F_]+|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?)(?:u8|u16|u32|u64|usize|i8|i16|i32|i64|f32|f64)?\b`;

const LANGS = {
  python: {
    keywords: PY_KEYWORDS,
    comment: String.raw`#[^\n]*`,
    string: String.raw`"""[\s\S]*?"""|'''[\s\S]*?'''|[rbf]?"(?:\\.|[^"\\\n])*"|[rbf]?'(?:\\.|[^'\\\n])*'`,
    extra: [["attr", String.raw`@[\w.]+`], ["type", String.raw`\b[A-Z][A-Za-z0-9_]*\b`]],
    flags: "gm",
  },
  sql: { keywords: SQL_KEYWORDS, comment: String.raw`--[^\n]*`, string: String.raw`'(?:''|[^'])*'`, extra: [], flags: "gmi" },
};

const compiled = {};

function pattern(lang) {
  const { keywords, comment, string, extra, flags } = LANGS[lang];
  const kw = keywords.split(" ").join("|");
  const parts = [
    `(?<comment>${comment})`,
    `(?<string>${string})`,
    `(?<number>${NUMBER})`,
    `(?<keyword>\\b(?:${kw})\\b)`,
    ...extra.map(([name, re]) => `(?<${name}>${re})`),
  ];
  return new RegExp(parts.join("|"), flags);
}

/** Text as HTML, escaped as Python's html.escape escapes it, so both lexers write the same. */
function escape(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
}

/** HTML for `code`, with spans classed `tok-<kind>` where the language is known. */
export function highlight(code, lang) {
  if (!LANGS[lang]) return escape(code);
  const re = (compiled[lang] ||= pattern(lang));
  re.lastIndex = 0;
  let out = "";
  let at = 0;
  for (const m of code.matchAll(re)) {
    const kind = Object.keys(m.groups).find((k) => m.groups[k] !== undefined);
    out += escape(code.slice(at, m.index)) + `<span class="tok-${kind}">${escape(m[0])}</span>`;
    at = m.index + m[0].length;
  }
  return out + escape(code.slice(at));
}

/** Colour `textarea` as `lang` as the reader types: a layer behind it draws the colours. */
export function colour(textarea, lang) {
  const box = document.createElement("div");
  box.className = "code-edit";
  const layer = document.createElement("pre");
  layer.className = "code-layer";
  layer.setAttribute("aria-hidden", "true");
  textarea.replaceWith(box);
  box.append(layer, textarea);
  // The layer must lay its text out exactly as the textarea does, whatever each editor's style.
  const style = getComputedStyle(textarea);
  // Longhands only: some browsers report a shorthand such as font as an empty string.
  const copied = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing", "tabSize"];
  for (const side of ["Top", "Right", "Bottom", "Left"]) copied.push(`padding${side}`, `border${side}Width`);
  for (const p of copied) layer.style[p] = style[p];
  layer.style.borderStyle = "solid";
  layer.style.borderColor = "transparent";
  textarea.wrap = "off";
  const draw = () => {
    // A final newline keeps the last line's height when the text ends in one.
    layer.innerHTML = `${highlight(textarea.value, lang)}\n`;
    layer.scrollTop = textarea.scrollTop;
    layer.scrollLeft = textarea.scrollLeft;
  };
  textarea.addEventListener("input", draw);
  textarea.addEventListener("scroll", () => {
    layer.scrollTop = textarea.scrollTop;
    layer.scrollLeft = textarea.scrollLeft;
  });
  draw();
  return draw;
}
