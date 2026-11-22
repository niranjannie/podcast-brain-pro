# Design contract

Podcast Brain Pro already has a product identity; preserve it. Existing implementation and tokens are the reference—do not import another brand's visual system.

## Product studio

- Dark, quiet console: deep neutral page, raised panel surfaces, subtle borders.
- One accent: indigo-to-cyan for primary actions and active navigation; semantic green/amber/red only for status.
- Tailwind tokens in `frontend/tailwind.config.ts` and global primitives in `frontend/app/globals.css` are authoritative.
- Reuse `Field`, `TextInput`, `TextArea`, `Select`, `SectionTitle`, `ErrorBanner`, `EmptyState`, `Button`, `Badge`, and `Modal` before adding primitives.
- Dense but readable: 14px body, 11–12px metadata, 8px spacing rhythm, rounded panels, no decorative motion that suggests false progress.
- Every control needs a visible label, keyboard focus, and loading/empty/error states with real data.
- Navigation is Create / Library / Voice Lab. Keep the same shell across product views.

## Marketing page

- Preserve the existing content hierarchy and identity. Optimize media and behavior rather than restyling it.
- Sample controls must use compressed, playable audio and honest loading states.

## Verification

Exercise changed surfaces in a real browser at desktop and mobile widths. Compilation alone is not visual verification.
