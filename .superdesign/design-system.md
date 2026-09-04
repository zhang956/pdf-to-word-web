# PDF 转 Word Web Design System

## Product context

This is a local, privacy-first document utility for converting one PDF at a time into an editable DOCX. The only page must make the primary job obvious: select or drop a PDF, start conversion, understand progress, and download the result. It supports text PDFs and scanned Chinese/English PDFs through local OCR. No account, navigation, pricing, cloud claims, or marketing sections are needed.

## Page architecture and states

- A compact top bar identifies the tool and communicates local processing/privacy.
- The main viewport centers one conversion workspace with an upload drop zone.
- Before selection: show accepted format, 50 MB limit, and a clear file-picker action.
- After selection: show filename and size, with replace/remove affordance and an enabled conversion button.
- During conversion: disable duplicate submission, show exact progress, current page, total pages, and a concise status label.
- On success: emphasize the DOCX download action and allow starting another conversion.
- On failure: show the server-provided Chinese error and a retry action without losing clarity.
- A compact support strip explains editable output, local OCR, and automatic file cleanup.

## Visual direction

Use the Mosaic Grid Architecture style as the only primary style source. The interface is technical minimalist, calm, and trustworthy rather than decorative.

- Background: Paper `#F7F7F5` with a very subtle rectilinear mosaic/grid pattern.
- Primary: Forest `#1A3C2B`.
- Text: Ink `#202320`; muted text `#626862`.
- Hairlines: `rgba(58, 58, 56, 0.20)`.
- Supporting status colors: Mint `#9EFFBF` for success, Gold `#F4D35E` for processing, Coral `#FF8C69` for errors only.
- Use no gradients and no box shadows.
- Corners are square or at most 2px radius.
- Use a system sans-serif stack for headings and body; use a system monospace stack for labels, metadata, progress, and file limits so the page works fully offline.

## Layout and spacing

- Desktop content width: up to 1120px, with the main converter arranged as a 7/5 split: upload and actions on the left, process explanation/status on the right.
- Mobile: one column, upload first, status and supporting details second.
- Use 1px section dividers and bento-like blocks separated by hairlines.
- Base spacing unit: 8px. Main workspace padding: 32-40px desktop, 20px mobile.
- Title should be prominent but sized for a utility, not a landing-page billboard.

## Components

- Upload zone: minimum 240px high, dashed 1px forest border, obvious keyboard focus, document/upload line icon, concise Chinese copy.
- Primary button: solid Forest background with white text, 48px minimum height, no shadow.
- Secondary button/link: transparent with 1px border.
- File card: flat white or Paper block with PDF badge, filename, size, and remove action.
- Progress: 6px flat track with solid Forest fill; pair with a monospaced numeric percentage and page count.
- Status badge: bordered inline container with a small square indicator and uppercase/technical metadata styling.
- Error: Coral left border and accessible text; never rely on color alone.

## Interaction and motion

- Hover/focus transitions use 140-180ms ease-out and change border/fill only.
- Drop-zone drag state uses a stronger Forest border and pale Mint fill.
- Progress changes animate linearly; honor `prefers-reduced-motion`.
- Every interactive element must have a visible keyboard focus outline.

## Content rules

- All visible product copy is concise Simplified Chinese.
- State exactly: supports text PDFs and scanned PDFs, maximum 50 MB, local OCR, editable output prioritized.
- Do not promise pixel-perfect layout preservation.
- Do not add testimonials, pricing, login, cloud upload claims, fake conversion history, or unsupported settings.
