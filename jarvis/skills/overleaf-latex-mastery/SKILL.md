---
name: overleaf-latex-mastery
description: Expert LaTeX and Overleaf workflow automation. Use this skill when authoring, structuring, validating, debugging, compiling, and packaging papers, resumes, theses, and reports for Overleaf or arXiv, including cross-disk zip preparation and bibliography synchronization.
category: publishing
---

# Overleaf & LaTeX Publishing Mastery

This skill equips JARVIS with full agentic competency for authoring, editing, validating, and packaging professional LaTeX documents compatible with Overleaf (TeX Live) and arXiv standards.

## Core Capabilities

1. **Cross-Disk Archive & Project Structuring**:
   - Access project files across any mounted disk (`C:\`, `D:\`, `G:\`).
   - Extract, surgically inspect, and repackage LaTeX `.zip` archives.
   - Flatten nested directory hierarchies so `main.tex` resides cleanly at the project root.

2. **Overleaf Compatibility Standards**:
   - **Entry Point**: Overleaf mandates a primary entry point (typically `main.tex`) containing `\documentclass` and `\begin{document}`.
   - **POSIX Slash Paths**: Overleaf compiles in a Linux environment. All file paths inside `\includegraphics{...}`, `\input{...}`, and `\bibliography{...}` must strictly use forward slashes `/`, never Windows backslashes `\`.
   - **Artifact Stripping**: Build artifacts (`.aux`, `.log`, `.out`, `.toc`, `.bbl`, `.blg`, `.synctex.gz`) and OS clutter (`__MACOSX`, `.DS_Store`, `Thumbs.db`) must be removed to avoid compilation conflicts and upload size limits.
   - **UTF-8 Encoding**: All files must be saved with UTF-8 encoding.

3. **Autonomous Validation Discipline (`validate_latex_project`)**:
   - Environment balance: Verify every `\begin{env}` has a corresponding `\end{env}`.
   - Figure integrity: Verify that all image assets referenced in `\includegraphics` exist on disk.
   - Bibliography integrity: Confirm that referenced `.bib` files exist and all `\cite{...}` keys are defined.
   - Syntax linting: Check for unescaped characters (`%`, `&`, `_`) outside allowed math/tabular environments.

4. **Surgical Editing & Assembly (`inspect_and_edit_archive`)**:
   - View, replace, add, or delete files directly inside a `.zip` archive without extracting the entire project.
   - Pull reference material from other folders or disks and inject them into the target LaTeX archive.

5. **Packaging for Overleaf (`prepare_overleaf_archive`)**:
   - Converts any directory or existing `.zip` into a pristine, verified Overleaf upload bundle.
   - The resulting archive can be uploaded directly via Overleaf: *New Project -> Upload Project*.
