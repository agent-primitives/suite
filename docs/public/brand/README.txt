AgentSuite identity assets

agentsuite.svg: hand-authored vector master, 64-unit square.
agentsuite.png: 512x512 raster export.
social-preview.png: 1280x640 repository social preview, for manual upload.

Regenerate PNG exports from the repository root:
  npm --prefix docs ci --ignore-scripts
  npm --prefix docs exec playwright install chromium
  npm --prefix docs run docs:brand

Family grammar for future sibling marks:
- 64-unit tile, 8-unit corner radius, inset 47-unit frame at 8.5.
- 1.5-unit frame, 2.5-unit connections, 3.5-unit node radius.
- Evergreen ground, mint connections/frame, near-paper nodes.
- Simple topology that remains legible at 32px; no letters or fine detail.
- Suite is a closed graph. Sessions and canvas can vary the internal topology
  while retaining the same frame, stroke and palette roles.

No stock or generated imagery is used. SVG geometry is the source of the mark;
PNG exports use the existing pinned Chromium renderer and local Public Sans.
The social-preview layout is authored in scripts/export-site-brand.mjs.
