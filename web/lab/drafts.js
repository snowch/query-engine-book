export const bookPath = location.pathname.replace(/[^/]*$/, "");

export const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
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
export function bindDraft(editor, { key, original, reset, recover, redraw, onChange, onMessage }) {
  const backup = `recovery:${key}`;
  const draft = (text) => text === original ? null : text;
  const update = () => {
    reset.hidden = editor.value === original;
    const saved = store.get(backup);
    recover.hidden = saved === null || saved === editor.value;
  };
  const switchTo = (text, message) => {
    const active = draft(editor.value);
    const saved = store.get(backup);
    const next = draft(text);
    // A reset must never discard text this browser could not back up. Recovery from the
    // original can move the backup only after putting it back into the active draft.
    const stashed = active === null || store.set(backup, active);
    if (!stashed || !store.set(key, next)) {
      if (stashed && active !== null) store.set(backup, saved);
      onMessage("This browser could not save a recovery copy. Your code is still in the editor.", true);
      return;
    }
    if (active === null) store.drop(backup);
    editor.value = text;
    redraw();
    onChange(true);
    onMessage(message);
    update();
    editor.focus();
  };

  editor.addEventListener("input", () => {
    if (!store.set(key, draft(editor.value))) onMessage("This browser could not save your draft.", true);
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
  update();
}
