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

  for (const raw of lines) {
    const line = raw.trim();
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
