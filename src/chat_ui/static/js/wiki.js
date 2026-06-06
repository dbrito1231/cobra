import { renderMarkdown } from "./markdown.js";

export class WikiPanel {
  constructor(contentEl, titleEl, backBtn) {
    this.contentEl = contentEl;
    this.titleEl = titleEl;
    this.backBtn = backBtn;
    this.currentPage = null;

    this.backBtn.addEventListener("click", () => this.loadIndex());
    this.contentEl.addEventListener("click", (e) => {
      const link = e.target.closest("[data-wiki-link]");
      if (!link) return;
      e.preventDefault();
      const target = link.dataset.wikiLink.replace(/\.md$/, "");
      this.loadPage(target);
    });
  }

  async loadIndex() {
    const data = await fetchJson("/api/wiki/index");
    this.currentPage = "index";
    this.titleEl.textContent = data.title || "Wiki Index";
    this.backBtn.hidden = true;
    this.renderPageLinks(data);
  }

  async loadPage(name) {
    const data = await fetchJson(`/api/wiki/page/${encodeURIComponent(name)}`);
    this.currentPage = name;
    this.titleEl.textContent = data.title || name;
    this.backBtn.hidden = name === "index";
    this.contentEl.innerHTML = renderMarkdown(data.content);
    this.wireInternalLinks();
  }

  async renderPageLinks(indexData) {
    const pages = await fetchJson("/api/wiki/pages");
    const items = pages.pages
      .filter((p) => p.name !== "index")
      .map(
        (p) =>
          `<li><a href="#" data-wiki-link="${p.path}">${escapeHtml(p.title)}</a></li>`
      )
      .join("");

    const body = renderMarkdown(indexData.content);
    this.contentEl.innerHTML =
      body +
      (items ? `<ul class="wiki-index-list">${items}</ul>` : "");
    this.wireInternalLinks();
  }

  wireInternalLinks() {
    this.contentEl.querySelectorAll("[data-wiki-link]").forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const target = link.dataset.wikiLink.replace(/\.md$/, "");
        this.loadPage(target);
      });
    });
  }
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed: ${url}`);
  return res.json();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
