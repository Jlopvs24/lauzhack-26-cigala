// Layout contract between the chat panel and the tree scene (#34).
//
// When the conversation opens, the panel takes the right side at full height (desktop) or
// becomes a bottom sheet (phones), and announces the space it takes so the scene can shrink
// into the remaining viewport and re-frame its camera, instead of being overlapped:
//   window 'panel:open'  CustomEvent, detail { side: 'right' | 'bottom', width, height }  (px)
//   window 'panel:close' CustomEvent, detail { side, width: 0, height: 0 }
//   :root CSS vars --chat-panel-w / --chat-panel-h (e.g. '400px' / '0px'), for CSS insets.
// 'panel:open' is fired again with new sizes when the window is resized while open.

export const PHONE_MAX = 720; // below this viewport width the panel is a bottom sheet
export const PANEL_MIN = 340;
export const PANEL_MAX = 440;
export const SHEET_SHARE = 0.62; // share of the viewport height taken by the bottom sheet

export function panelLayout(viewportWidth, viewportHeight) {
  const w = Math.max(0, Number(viewportWidth) || 0);
  const h = Math.max(0, Number(viewportHeight) || 0);
  if (w < PHONE_MAX) return { side: 'bottom', width: w, height: Math.round(h * SHEET_SHARE) };
  const width = Math.round(Math.min(PANEL_MAX, Math.max(PANEL_MIN, w * 0.3)));
  return { side: 'right', width, height: h };
}

// Space the scene loses: a right panel removes width, a bottom sheet removes height.
export function insets(layout, open) {
  if (!open) return { right: 0, bottom: 0 };
  return layout.side === 'right' ? { right: layout.width, bottom: 0 } : { right: 0, bottom: layout.height };
}

export function announcePanel(open, layout, { target = globalThis, root = globalThis.document?.documentElement } = {}) {
  const inset = insets(layout, open);
  root?.style?.setProperty('--chat-panel-w', `${inset.right}px`);
  root?.style?.setProperty('--chat-panel-h', `${inset.bottom}px`);
  const detail = open ? { side: layout.side, width: layout.width, height: layout.height }
    : { side: layout.side, width: 0, height: 0 };
  const name = open ? 'panel:open' : 'panel:close';
  target?.dispatchEvent?.(new CustomEvent(name, { detail }));
  return { name, detail };
}
