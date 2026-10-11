---
name: archive-data-orchestrator
description: Comprehensive multi-disk file and archive orchestration. Use this skill when managing, inspecting, surgically editing, extracting, and packaging zip, tar, and gzip files across multiple PC drives (C:, D:, G:, etc.), referencing external folders, and synchronizing workspace assets.
category: system
---

# Archive & Multi-Disk Data Orchestrator

This skill enables JARVIS to operate across multiple storage drives, partitions, and archive formats with the same precision and versatility as Antigravity.

## Workflow Principles

1. **Multi-Disk Navigation**:
   - Seamlessly read, reference, and modify files located across all system storage drives (`C:\`, `D:\`, `G:\`, etc.).
   - Access reference assets, source code, data sets, or documentation from any drive to synthesize or modify projects.
   - Operating system and credential directories remain safeguarded by `BLOCKED_PATTERNS`.

2. **In-Place & Surgical Archive Operations**:
   - **Inspection Without Unpacking**: Call `list_archive` to view directory layouts or `inspect_and_edit_archive(..., action="view")` to inspect individual files.
   - **Surgical Insertion & Replacement**: Use `inspect_and_edit_archive(..., action="replace", replacement_content="...")` or `new_file_source="..."` to update a single file inside an archive atomically.
   - **Targeted Extraction**: Extract single files on demand via `action="extract_file"` rather than unzipping massive archives.

3. **Multi-Format Extraction & Compression**:
   - Extract `.zip`, `.tar`, `.tar.gz`, and `.tgz` archives with directory-traversal security verification (`extract_archive`).
   - Create standardized `.zip` bundles using `create_archive` or specialized Overleaf archives using `prepare_overleaf_archive`.

4. **Cross-Referencing & Data Transformation**:
   - Read configurations or data from disk A, transform into target format (JSON, YAML, BibTeX, Markdown), and inject into archive or workspace on disk B.
