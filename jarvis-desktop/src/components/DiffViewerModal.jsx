import React, { useState, useEffect, useMemo, useRef } from 'react'
import './DiffViewer.css'

/**
 * Parses raw unified diff string into structured file diffs and hunks.
 */
function parseDiff(rawDiff) {
  if (!rawDiff || typeof rawDiff !== 'string') {
    return []
  }

  const lines = rawDiff.split(/\r?\n/)
  const files = []
  let currentFile = null
  let currentHunk = null
  let oldLineCounter = 0
  let newLineCounter = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Check for git diff file header
    if (line.startsWith('diff --git ')) {
      const match = line.match(/^diff --git a\/(.+?) b\/(.+)$/)
      const oldPath = match ? match[1] : ''
      const newPath = match ? match[2] : ''
      const displayPath = newPath || oldPath || 'unnamed'
      const parts = displayPath.split('/')
      const fileName = parts[parts.length - 1]

      currentFile = {
        oldPath,
        newPath,
        filePath: displayPath,
        fileName,
        status: 'modified',
        additions: 0,
        deletions: 0,
        hunks: []
      }
      files.push(currentFile)
      currentHunk = null
      continue
    }

    // Detect file mode / status changes
    if (currentFile) {
      if (line.startsWith('new file mode')) {
        currentFile.status = 'added'
        continue
      }
      if (line.startsWith('deleted file mode')) {
        currentFile.status = 'deleted'
        continue
      }
      if (line.startsWith('similarity index') || line.startsWith('rename from')) {
        currentFile.status = 'renamed'
        continue
      }
    }

    // Fallback for plain patch without 'diff --git'
    if (!currentFile && (line.startsWith('--- ') || line.startsWith('+++ '))) {
      let p = line.slice(4).trim()
      p = p.replace(/^[ab]\//, '')
      const parts = p.split('/')
      currentFile = {
        oldPath: p,
        newPath: p,
        filePath: p,
        fileName: parts[parts.length - 1] || 'diff.patch',
        status: 'modified',
        additions: 0,
        deletions: 0,
        hunks: []
      }
      files.push(currentFile)
      currentHunk = null
    }

    // Detect hunk header: @@ -oldStart,oldCount +newStart,newCount @@
    if (line.startsWith('@@ ')) {
      if (!currentFile) {
        currentFile = {
          oldPath: 'changes',
          newPath: 'changes',
          filePath: 'changes',
          fileName: 'changes.diff',
          status: 'modified',
          additions: 0,
          deletions: 0,
          hunks: []
        }
        files.push(currentFile)
      }

      const match = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$/)
      if (match) {
        const oldStart = parseInt(match[1], 10)
        const oldCount = match[2] !== undefined ? parseInt(match[2], 10) : 1
        const newStart = parseInt(match[3], 10)
        const newCount = match[4] !== undefined ? parseInt(match[4], 10) : 1
        const heading = match[5] ? match[5].trim() : ''

        oldLineCounter = oldStart
        newLineCounter = newStart

        currentHunk = {
          header: line,
          heading,
          oldStart,
          oldCount,
          newStart,
          newCount,
          lines: []
        }
        currentFile.hunks.push(currentHunk)
        continue
      }
    }

    // If inside a hunk, parse the line content
    if (currentHunk) {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        currentFile.additions++
        currentHunk.lines.push({
          type: 'addition',
          content: line.slice(1),
          oldLineNum: null,
          newLineNum: newLineCounter++
        })
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        currentFile.deletions++
        currentHunk.lines.push({
          type: 'deletion',
          content: line.slice(1),
          oldLineNum: oldLineCounter++,
          newLineNum: null
        })
      } else if (line.startsWith(' ')) {
        currentHunk.lines.push({
          type: 'context',
          content: line.slice(1),
          oldLineNum: oldLineCounter++,
          newLineNum: newLineCounter++
        })
      } else if (line.startsWith('\\')) {
        currentHunk.lines.push({
          type: 'meta',
          content: line,
          oldLineNum: null,
          newLineNum: null
        })
      } else if (line.length > 0 && !line.startsWith('index ') && !line.startsWith('--- ') && !line.startsWith('+++ ')) {
        // Tolerant context fallback
        currentHunk.lines.push({
          type: 'context',
          content: line,
          oldLineNum: oldLineCounter++,
          newLineNum: newLineCounter++
        })
      }
    }
  }

  return files
}

/**
 * Transforms hunk lines into aligned side-by-side split rows.
 */
function buildSplitRows(lines) {
  const rows = []
  let pendingDeletions = []
  let pendingAdditions = []

  const flushPending = () => {
    const maxLen = Math.max(pendingDeletions.length, pendingAdditions.length)
    for (let i = 0; i < maxLen; i++) {
      rows.push({
        left: pendingDeletions[i] || { type: 'empty', lineNum: null, content: '' },
        right: pendingAdditions[i] || { type: 'empty', lineNum: null, content: '' }
      })
    }
    pendingDeletions = []
    pendingAdditions = []
  }

  for (const line of lines) {
    if (line.type === 'deletion') {
      pendingDeletions.push({ type: 'deletion', lineNum: line.oldLineNum, content: line.content })
    } else if (line.type === 'addition') {
      pendingAdditions.push({ type: 'addition', lineNum: line.newLineNum, content: line.content })
    } else if (line.type === 'context') {
      flushPending()
      rows.push({
        left: { type: 'context', lineNum: line.oldLineNum, content: line.content },
        right: { type: 'context', lineNum: line.newLineNum, content: line.content }
      })
    } else if (line.type === 'meta') {
      flushPending()
      rows.push({
        left: { type: 'meta', lineNum: null, content: line.content },
        right: { type: 'meta', lineNum: null, content: line.content }
      })
    }
  }
  flushPending()
  return rows
}

export default function DiffViewerModal({
  isOpen,
  onClose,
  diffText = '',
  summary = '',
  onRefresh
}) {
  const [viewMode, setViewMode] = useState('unified') // 'unified' | 'split'
  const [selectedFileIndex, setSelectedFileIndex] = useState(0)
  const [fileFilter, setFileFilter] = useState('')
  const [copied, setCopied] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const modalRef = useRef(null)

  // Parse diff files
  const parsedFiles = useMemo(() => parseDiff(diffText), [diffText])

  // Aggregate stats
  const totals = useMemo(() => {
    let additions = 0
    let deletions = 0
    for (const f of parsedFiles) {
      additions += f.additions
      deletions += f.deletions
    }
    return {
      fileCount: parsedFiles.length,
      additions,
      deletions
    }
  }, [parsedFiles])

  // Filtered files list for tabs
  const filteredFiles = useMemo(() => {
    if (!fileFilter.trim()) return parsedFiles
    const q = fileFilter.toLowerCase()
    return parsedFiles.filter(f => f.filePath.toLowerCase().includes(q))
  }, [parsedFiles, fileFilter])

  // Active file
  const activeFile = parsedFiles[selectedFileIndex] || parsedFiles[0] || null

  // Ensure selected index stays in bounds
  useEffect(() => {
    if (selectedFileIndex >= parsedFiles.length && parsedFiles.length > 0) {
      setSelectedFileIndex(0)
    }
  }, [parsedFiles, selectedFileIndex])

  // Keyboard shortcut listener (ESC to close, u/s to switch views)
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose && onClose()
      } else if ((e.key === 'u' || e.key === 'U') && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
        setViewMode('unified')
      } else if ((e.key === 's' || e.key === 'S') && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
        setViewMode('split')
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  const handleCopyDiff = () => {
    const textToCopy = diffText || ''
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  const handleRefreshClick = async () => {
    if (onRefresh && !isRefreshing) {
      setIsRefreshing(true)
      try {
        await onRefresh()
      } finally {
        setTimeout(() => setIsRefreshing(false), 500)
      }
    }
  }

  if (!isOpen) return null

  const isClean = !parsedFiles.length || (!totals.additions && !totals.deletions && (!diffText || diffText.includes('No changes')))

  return (
    <div className="diff-modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="diff-modal-window" ref={modalRef}>
        
        {/* HUD Header */}
        <div className="diff-modal-header">
          <div className="diff-header-left">
            <span className="diff-hud-symbol">⎊</span>
            <div className="diff-header-title-block">
              <span className="diff-header-title">STARK HUD // VISUAL DIFF INSPECTOR</span>
              <span className="diff-header-sub">MARK 5.7 WORKSPACE CODE AUDIT</span>
            </div>
            {!isClean && (
              <div className="diff-stat-pills">
                <span className="diff-pill files">{totals.fileCount} {totals.fileCount === 1 ? 'FILE' : 'FILES'}</span>
                <span className="diff-pill add">+{totals.additions}</span>
                <span className="diff-pill del">-{totals.deletions}</span>
              </div>
            )}
          </div>

          <div className="diff-header-actions">
            {/* View Mode Switcher */}
            <div className="diff-view-mode-toggle">
              <button
                className={`diff-mode-btn ${viewMode === 'unified' ? 'active' : ''}`}
                onClick={() => setViewMode('unified')}
                title="Unified View (U)"
              >
                ⊟ UNIFIED
              </button>
              <button
                className={`diff-mode-btn ${viewMode === 'split' ? 'active' : ''}`}
                onClick={() => setViewMode('split')}
                title="Side-by-Side Split View (S)"
              >
                ◫ SPLIT
              </button>
            </div>

            {/* Refresh Action */}
            {onRefresh && (
              <button
                className={`diff-action-btn ${isRefreshing ? 'spinning' : ''}`}
                onClick={handleRefreshClick}
                title="Refresh Workspace Diff"
              >
                ⟳ REFRESH
              </button>
            )}

            {/* Copy Action */}
            <button
              className="diff-action-btn"
              onClick={handleCopyDiff}
              title="Copy Raw Diff to Clipboard"
            >
              {copied ? '✓ COPIED' : '📋 COPY'}
            </button>

            {/* Close Button */}
            <button
              className="diff-action-btn close-btn"
              onClick={onClose}
              title="Close Inspector (ESC)"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Multi-File Tab Bar */}
        {parsedFiles.length > 1 && (
          <div className="diff-files-bar">
            {parsedFiles.length > 5 && (
              <div className="diff-filter-input-wrap">
                <input
                  type="text"
                  className="diff-filter-input"
                  placeholder="Filter files..."
                  value={fileFilter}
                  onChange={(e) => setFileFilter(e.target.value)}
                />
              </div>
            )}
            <div className="diff-files-tabs">
              {filteredFiles.map((file) => {
                const origIdx = parsedFiles.indexOf(file)
                const isSelected = origIdx === selectedFileIndex
                return (
                  <button
                    key={file.filePath}
                    className={`diff-file-tab ${isSelected ? 'active' : ''}`}
                    onClick={() => setSelectedFileIndex(origIdx)}
                  >
                    <span className={`diff-tab-status ${file.status}`}>
                      {file.status === 'added' ? '+' : file.status === 'deleted' ? '−' : 'M'}
                    </span>
                    <span className="diff-tab-name" title={file.filePath}>{file.fileName}</span>
                    <span className="diff-tab-counts">
                      {file.additions > 0 && <span className="tab-add">+{file.additions}</span>}
                      {file.deletions > 0 && <span className="tab-del">-{file.deletions}</span>}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Active File Header info */}
        {activeFile && !isClean && (
          <div className="diff-active-file-header">
            <span className="diff-active-path">
              <span className="diff-path-prefix">{activeFile.status.toUpperCase()} // </span>
              {activeFile.filePath}
            </span>
            <div className="diff-active-stats">
              <span className="active-stat-add">+{activeFile.additions} lines</span>
              <span className="divider-dot">•</span>
              <span className="active-stat-del">-{activeFile.deletions} lines</span>
              <span className="divider-dot">•</span>
              <span className="active-hunk-count">{activeFile.hunks.length} {activeFile.hunks.length === 1 ? 'hunk' : 'hunks'}</span>
            </div>
          </div>
        )}

        {/* Diff Content Body */}
        <div className="diff-modal-body">
          {isClean ? (
            <div className="diff-clean-state">
              <div className="clean-reticle">⎊</div>
              <h3 className="clean-title">WORKSPACE WORKING TREE CLEAN</h3>
              <p className="clean-desc">
                No uncommitted changes detected against git HEAD.
              </p>
              {summary && <div className="clean-summary-box">{summary}</div>}
              <div className="clean-actions">
                {onRefresh && (
                  <button className="diff-action-btn clean-refresh" onClick={handleRefreshClick}>
                    ⟳ SCAN WORKSPACE NOW
                  </button>
                )}
                <button className="diff-action-btn" onClick={onClose}>
                  DISMISS
                </button>
              </div>
            </div>
          ) : !activeFile ? (
            <div className="diff-clean-state">
              <p className="clean-desc">No matching files found for filter "{fileFilter}".</p>
            </div>
          ) : viewMode === 'unified' ? (
            /* UNIFIED VIEW */
            <div className="diff-unified-view">
              {activeFile.hunks.map((hunk, hIdx) => (
                <div key={hIdx} className="diff-hunk-block">
                  <div className="diff-hunk-header">
                    <span className="hunk-header-symbol">@@</span>
                    <span className="hunk-header-text">{hunk.header}</span>
                    {hunk.heading && <span className="hunk-heading-scope">{hunk.heading}</span>}
                  </div>
                  <div className="diff-hunk-lines">
                    {hunk.lines.map((line, lIdx) => (
                      <div key={lIdx} className={`diff-line unified ${line.type}`}>
                        <div className="diff-gutter old-num">
                          {line.oldLineNum !== null ? line.oldLineNum : ''}
                        </div>
                        <div className="diff-gutter new-num">
                          {line.newLineNum !== null ? line.newLineNum : ''}
                        </div>
                        <div className="diff-gutter marker">
                          {line.type === 'addition' ? '+' : line.type === 'deletion' ? '−' : ' '}
                        </div>
                        <div className="diff-code-content">
                          {line.content || ' '}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* SPLIT (SIDE-BY-SIDE) VIEW */
            <div className="diff-split-view">
              <div className="diff-split-columns-header">
                <div className="split-col-title left">
                  <span>BASE // PREVIOUS</span>
                </div>
                <div className="split-col-title right">
                  <span>WORKING // CURRENT</span>
                </div>
              </div>

              {activeFile.hunks.map((hunk, hIdx) => {
                const splitRows = buildSplitRows(hunk.lines)
                return (
                  <div key={hIdx} className="diff-hunk-block">
                    <div className="diff-hunk-header">
                      <span className="hunk-header-symbol">@@</span>
                      <span className="hunk-header-text">{hunk.header}</span>
                      {hunk.heading && <span className="hunk-heading-scope">{hunk.heading}</span>}
                    </div>

                    <div className="diff-split-rows">
                      {splitRows.map((row, rIdx) => (
                        <div key={rIdx} className="diff-split-row">
                          {/* Left Column (Old / Deletion) */}
                          <div className={`diff-split-cell left ${row.left.type}`}>
                            <div className="diff-gutter split-num">
                              {row.left.lineNum !== null ? row.left.lineNum : ''}
                            </div>
                            <div className="diff-gutter marker">
                              {row.left.type === 'deletion' ? '−' : ' '}
                            </div>
                            <div className="diff-code-content">
                              {row.left.content || (row.left.type === 'empty' ? '' : ' ')}
                            </div>
                          </div>

                          {/* Right Column (New / Addition) */}
                          <div className={`diff-split-cell right ${row.right.type}`}>
                            <div className="diff-gutter split-num">
                              {row.right.lineNum !== null ? row.right.lineNum : ''}
                            </div>
                            <div className="diff-gutter marker">
                              {row.right.type === 'addition' ? '+' : ' '}
                            </div>
                            <div className="diff-code-content">
                              {row.right.content || (row.right.type === 'empty' ? '' : ' ')}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer Bar */}
        <div className="diff-modal-footer">
          <div className="footer-legend">
            <span className="legend-item"><span className="legend-box add"></span> Addition</span>
            <span className="legend-item"><span className="legend-box del"></span> Deletion</span>
            <span className="legend-item"><span className="legend-box hunk"></span> Hunk Header</span>
          </div>
          <div className="footer-keys">
            <span className="key-hint"><kbd>U</kbd> Unified</span>
            <span className="key-hint"><kbd>S</kbd> Split</span>
            <span className="key-hint"><kbd>ESC</kbd> Close</span>
          </div>
        </div>

      </div>
    </div>
  )
}
