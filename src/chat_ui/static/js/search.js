export class SearchOverlay {
  constructor(overlayEl, inputEl, resultsEl, closeBtn) {
    this.overlayEl = overlayEl;
    this.inputEl = inputEl;
    this.resultsEl = resultsEl;
    this.closeBtn = closeBtn;
    this.debounceTimer = null;
    this.onJump = null;

    this.closeBtn.addEventListener("click", () => this.close());
    this.overlayEl.addEventListener("click", (e) => {
      if (e.target === this.overlayEl) this.close();
    });
    this.inputEl.addEventListener("input", () => this.debouncedSearch());
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !this.overlayEl.hidden) this.close();
    });
  }

  open() {
    this.overlayEl.hidden = false;
    this.inputEl.value = "";
    this.resultsEl.innerHTML = "";
    this.inputEl.focus();
  }

  close() {
    this.overlayEl.hidden = true;
  }

  debouncedSearch() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.search(), 200);
  }

  async search() {
    const q = this.inputEl.value.trim();
    if (!q) {
      this.resultsEl.innerHTML = "";
      return;
    }

    const data = await fetch(`/api/search?q=${encodeURIComponent(q)}`).then((r) =>
      r.json()
    );
    this.renderResults(data.results || []);
  }

  renderResults(results) {
    this.resultsEl.innerHTML = "";
    if (!results.length) {
      this.resultsEl.innerHTML = '<li class="search-empty">No results found</li>';
      return;
    }

    results.forEach((result) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <div class="search-result-meta">${escapeHtml(result.session_date)} · ${escapeHtml(result.sender)}</div>
        <div class="search-result-excerpt">${escapeHtml(result.excerpt)}</div>
      `;
      li.addEventListener("click", () => {
        this.onJump?.(result);
        this.close();
      });
      this.resultsEl.appendChild(li);
    });
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
