export const bookPath = location.pathname.replace(/[^/]*$/, "");

export const store = {
  read(key) { try { return localStorage.getItem(key); } catch { return undefined; } },
  get(key) { return this.read(key) ?? null; },
  set(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
      return true;
    } catch {
      return false;
    }
  },
  drop(key) { return store.set(key, null); },
};

// Keep the existing active-draft key. A reset saves one recovery copy before replacing the code.
export function bindDraft(editor, { key, original, reset, recover, redraw, onChange, filename }) {
  const backup = `recovery:${key}`;
  const saveStatus = document.createElement("span");
  saveStatus.className = "draft-status";
  saveStatus.setAttribute("role", "status");
  const download = document.createElement("button");
  download.className = "draft-download";
  download.type = "button";
  download.textContent = "Download editor text";
  download.hidden = true;
  recover.after(download, saveStatus);
  download.addEventListener("click", () => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([editor.value], { type: "text/plain;charset=utf-8" }));
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1_000);
  });
  const message = (text, error = false, offerDownload = error) => {
    saveStatus.textContent = text;
    saveStatus.classList.toggle("lab-error", error);
    download.hidden = !offerDownload;
  };
  const draft = (text) => text === original ? null : text;
  const update = () => {
    reset.hidden = editor.value === original;
    const saved = store.get(backup);
    recover.hidden = saved === null || saved === editor.value;
  };
  const switchTo = (text, success) => {
    const active = draft(editor.value);
    const saved = store.read(backup);
    if (saved === undefined) {
      message("This browser could not read the recovery copy. Your text is still in the editor. Download it before leaving.", true);
      return;
    }
    const next = draft(text);
    // A reset must never discard text this browser could not back up. Recovery from the
    // original can move the backup only after putting it back into the active draft.
    const stashed = active === null || store.set(backup, active);
    if (!stashed || !store.set(key, next)) {
      if (stashed && active !== null) store.set(backup, saved);
      message("This browser could not save a recovery copy. Your text is still in the editor. Download it before leaving.", true);
      return;
    }
    if (active === null) store.drop(backup);
    editor.value = text;
    redraw();
    onChange(true);
    message(success);
    update();
    editor.focus();
  };

  editor.addEventListener("input", () => {
    if (store.set(key, draft(editor.value))) message("");
    else message("This browser could not save your draft. Download the editor text before leaving.", true);
    onChange(false);
    update();
  });
  reset.addEventListener("click", () => {
    if (editor.value !== original) switchTo(original, "Restored the starter. Use Recover saved draft to get your work back.");
  });
  recover.addEventListener("click", () => {
    const saved = store.get(backup);
    if (saved !== null && saved !== editor.value) switchTo(saved, "Recovered your saved draft. Run it to see the result.");
  });
  const saved = store.read(key);
  if (saved === undefined) message("This browser could not read saved drafts.", true, editor.value !== original);
  else if ((saved ?? original) !== editor.value) {
    message("This browser could not save your draft. Download the editor text before leaving.", true);
  }
  update();
}
