# EmbodiWeave design guide

## Direction
A robotics test lab on engineering paper. Existing product identity takes precedence over generic templates. Every visual claim must be supported by simulator or graph evidence.

## Foundations
- Paper #f4f2ec, surface #fbfaf7, graphite #1b2026, muted #555b62, rules #d6d2c6.
- Safety orange #b93d0b for readable accents; #ea580c for robot geometry. Semantic green and red only for measured state, blue for the pedestrian and recorded labels.
- Space Grotesk for display, IBM Plex Sans for text, IBM Plex Mono for code, identifiers and tabular data.
- 24px engineering grid, restrained borders and 8–12px radii. No stock AI illustrations or invented robot footage.

## Information architecture
- Landing: paired recorded replay, live FalkorDB console, selection, gate, experiments and schema.
- Judge guide: short route, live/recorded/local boundaries, demo film, graph rationale, local reproduction and limitations.
- Studio: detailed evidence and interactive local workflows. Public hosted controls explain why training and launches are disabled.

## Signature interaction
Replay two recorded episodes on seed 1300032. Deployed policy collision at step 51; new checkpoint goal at step 112. Keep aggregate validation separate: 87% success, 13% collision, promotion rejected. Do not imply one successful episode passed the overall gate.

## Motion
Entrance 500ms, stagger 80–180ms, section reveal 320ms, feedback 120–240ms; cubic-bezier(.2,0,0,1). Animate opacity and transform. Respect prefers-reduced-motion: no automatic replay, show final frame, no entrance or pulse animation. Preserve visible content if JavaScript fails.

## Responsive and accessible
Test 360, 768 and 1440px. No document overflow; code and tables may scroll inside labelled focusable regions. Minimum 40px controls, visible keyboard focus, semantic landmarks and skip link. Body contrast at least 4.5:1. Keep labels alongside state colors. Mobile sections stack with legible typography.

## Evidence boundaries
Live means a query was executed against the running FalkorDB graph. Recorded means immutable stored training, evaluation or runtime agent evidence. What-if means an isolated GRAPH.COPY sandbox. Local means work requiring the full CPU stack and explicit provider consent. Graph outage must be visible; never fill live fields with fabricated values.

Apply the custom-design skill using these project constraints. Changes must retain the rejected outcome and preliminary benchmark limitations.
