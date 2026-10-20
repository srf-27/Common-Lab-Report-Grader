import { useEffect, useRef } from "react";

const escapeHtml = (text) =>
  String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const inline = (text) =>
  text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");

function toHtml(text) {
  const lines = escapeHtml(text).split(/\r?\n/);
  const out = [];
  let list = null;
  let para = [];
  let math = false;
  const closeList = () => {
    if (list) {
      out.push(`</${list}>`);
      list = null;
    }
  };
  const closePara = () => {
    if (para.length) {
      out.push(`<p>${para.map(inline).join("\n")}</p>`);
      para = [];
    }
  };
  const cellsOf = (line) =>
    line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    // 公式块可能跨空行，块内不切段，否则 \[ 与 \] 会落进不同 <p>，KaTeX 无法识别
    if (math) {
      para.push(line);
      if (line.includes("\\]")) math = false;
      continue;
    }
    if (!line) {
      closePara();
      closeList();
      continue;
    }
    // Markdown 表格：表头 + |---| 分隔行，直到出现非表格行
    if (
      line.startsWith("|") &&
      index + 1 < lines.length &&
      /^\|[\s:|-]+\|$/.test(lines[index + 1].trim())
    ) {
      closePara();
      closeList();
      const head = cellsOf(line);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        rows.push(cellsOf(lines[index]));
        index += 1;
      }
      index -= 1;
      out.push('<div class="table-wrap"><table><thead><tr>');
      head.forEach((cell) => out.push(`<th>${inline(cell)}</th>`));
      out.push("</tr></thead><tbody>");
      rows.forEach((row) => {
        out.push("<tr>");
        head.forEach((_, cellIndex) => out.push(`<td>${inline(row[cellIndex] || "")}</td>`));
        out.push("</tr>");
      });
      out.push("</tbody></table></div>");
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      closePara();
      closeList();
      const level = Math.min(heading[1].length + 2, 6);
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = line.match(/^[-*·]\s+(.*)$/);
    if (bullet) {
      closePara();
      if (list !== "ul") {
        closeList();
        out.push("<ul>");
        list = "ul";
      }
      out.push(`<li>${inline(bullet[1])}</li>`);
      continue;
    }
    const ordered = line.match(/^\d+[.)]\s+(.*)$/);
    if (ordered) {
      closePara();
      if (list !== "ol") {
        closeList();
        out.push("<ol>");
        list = "ol";
      }
      out.push(`<li>${inline(ordered[1])}</li>`);
      continue;
    }
    closeList();
    para.push(line);
    if (line.includes("\\[") && !line.includes("\\]")) math = true;
  }
  closePara();
  closeList();
  return out.join("");
}

const DELIMITERS = [
  { left: "$$", right: "$$", display: true },
  { left: "\\[", right: "\\]", display: true },
  { left: "\\(", right: "\\)", display: false },
];

export function Prose({ text }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || typeof window.renderMathInElement !== "function") return;
    try {
      window.renderMathInElement(ref.current, {
        delimiters: DELIMITERS,
        throwOnError: false,
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
      });
    } catch {
      /* 公式渲染失败时保留原文 */
    }
  }, [text]);

  return <div ref={ref} className="prose" dangerouslySetInnerHTML={{ __html: toHtml(text) }} />;
}
