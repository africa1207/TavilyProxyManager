export async function writeClipboardText(text: string): Promise<void> {
  if (!text) return;

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fall back to execCommand below.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "0";
  textarea.style.width = "1px";
  textarea.style.height = "1px";
  textarea.style.padding = "0";
  textarea.style.border = "none";
  textarea.style.outline = "none";
  textarea.style.boxShadow = "none";
  textarea.style.background = "transparent";
  textarea.style.opacity = "0";

  document.body.appendChild(textarea);
  try {
    textarea.focus();
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);

    if (!document.execCommand("copy")) {
      throw new Error("copy_failed");
    }
  } finally {
    textarea.remove();
  }
}
