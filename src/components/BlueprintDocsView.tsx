import React, { useState } from 'react';
import {
  FileText,
  HardDrive,
  ExternalLink,
  BookOpen,
  Search,
  CheckCircle2,
  Lock,
  Code2,
  Terminal,
  Shield,
  RefreshCw,
  Eye,
} from 'lucide-react';
import { CANONICAL_BLUEPRINT_DOCS } from '../data/canonicalBlueprint';
import { DriveBlueprintItem } from '../types/trading';

interface BlueprintDocsViewProps {
  driveFiles: DriveBlueprintItem[];
  driveConnected: boolean;
  isLoadingDrive: boolean;
  onRefreshDrive: () => void;
  onOpenDriveModal: () => void;
  onSelectDriveFile: (file: DriveBlueprintItem) => void;
  selectedFileContent: string | null;
  selectedFile: DriveBlueprintItem | null;
}

export const BlueprintDocsView: React.FC<BlueprintDocsViewProps> = ({
  driveFiles,
  driveConnected,
  isLoadingDrive,
  onRefreshDrive,
  onOpenDriveModal,
  onSelectDriveFile,
  selectedFileContent,
  selectedFile,
}) => {
  const [activeSection, setActiveSection] = useState<'CANONICAL' | 'DRIVE_FILES' | 'MATH_FORMULAS'>('CANONICAL');

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-amber-400" />
              <h2 className="text-base font-bold text-slate-100 font-mono tracking-tight">
                OMEGA NIO BLUEPRINT &amp; SPECIFICATION ENGINE
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-3xl">
              Canonical architecture specifications, mathematical risk derivations, and direct Google Drive file synchronization for the OMEGA NIO and Sigma Alpha quant systems.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onOpenDriveModal}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-semibold bg-blue-600/20 text-blue-300 border border-blue-500/40 hover:bg-blue-600/30 transition-colors"
            >
              <HardDrive className="w-3.5 h-3.5" />
              <span>{driveConnected ? 'Manage Drive Sync' : 'Connect Google Drive'}</span>
            </button>

            {driveConnected && (
              <button
                onClick={onRefreshDrive}
                disabled={isLoadingDrive}
                className="p-1.5 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors border border-slate-700"
                title="Refresh Drive Search"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingDrive ? 'animate-spin' : ''}`} />
              </button>
            )}
          </div>
        </div>

        {/* Section Navigation Tabs */}
        <div className="flex items-center gap-2 mt-3 pt-1">
          <button
            onClick={() => setActiveSection('CANONICAL')}
            className={`px-3 py-1 rounded text-xs font-mono font-medium transition-colors ${
              activeSection === 'CANONICAL'
                ? 'bg-slate-800 text-amber-400 border border-slate-700'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            System Blueprint &amp; Zero-Dummy
          </button>
          <button
            onClick={() => setActiveSection('DRIVE_FILES')}
            className={`px-3 py-1 rounded text-xs font-mono font-medium transition-colors flex items-center gap-1.5 ${
              activeSection === 'DRIVE_FILES'
                ? 'bg-slate-800 text-amber-400 border border-slate-700'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>Google Drive Files</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-500/20 text-blue-300">
              {driveFiles.length}
            </span>
          </button>
          <button
            onClick={() => setActiveSection('MATH_FORMULAS')}
            className={`px-3 py-1 rounded text-xs font-mono font-medium transition-colors ${
              activeSection === 'MATH_FORMULAS'
                ? 'bg-slate-800 text-amber-400 border border-slate-700'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Mathematical Invariants
          </button>
        </div>
      </div>

      {/* Section 1: Canonical Blueprint & Directives */}
      {activeSection === 'CANONICAL' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-8 space-y-4">
            {/* Zero Dummy Directive Card */}
            <div className="bg-slate-900 border border-emerald-500/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-bold font-mono text-emerald-400">
                  {CANONICAL_BLUEPRINT_DOCS.zeroDummyDirective.split(':')[0]}
                </h3>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-mono">
                {CANONICAL_BLUEPRINT_DOCS.zeroDummyDirective}
              </p>
              <div className="mt-3 pt-2 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] font-mono text-slate-400">
                <div className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>No Stubs / No Pass Logics</span>
                </div>
                <div className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Strict TypeScript Typing</span>
                </div>
                <div className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Closed Math Formulas</span>
                </div>
              </div>
            </div>

            {/* Architecture Separation Philosophy */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
              <h3 className="text-xs font-bold font-mono text-amber-400 uppercase tracking-wider mb-2">
                Core Architectural Division: The Judge vs The Swarm
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed font-mono mb-3">
                {CANONICAL_BLUEPRINT_DOCS.philosophy}
              </p>
              <p className="text-xs text-slate-400 leading-relaxed">
                {CANONICAL_BLUEPRINT_DOCS.systemArchitecture}
              </p>
            </div>

            {/* 8 Gates Specification Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
              <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider mb-3">
                Gate Specification Matrix (M1 through M8)
              </h3>
              <div className="space-y-2">
                {CANONICAL_BLUEPRINT_DOCS.gateSpecifications.map((gate) => (
                  <div
                    key={gate.gateId}
                    className="p-2.5 rounded bg-slate-950 border border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono"
                  >
                    <div className="flex items-start gap-2">
                      <span className="font-bold text-amber-400 px-1.5 py-0.5 rounded bg-amber-400/10 text-xs">
                        {gate.gateId}
                      </span>
                      <div>
                        <span className="font-bold text-slate-200">{gate.name}</span>
                        <p className="text-[11px] text-slate-400 mt-0.5">{gate.description}</p>
                      </div>
                    </div>

                    <div className="text-right whitespace-nowrap pl-6 sm:pl-0">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {gate.strictness}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: GitHub & System Reference Links (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
              <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider mb-3">
                External Systems &amp; Source References
              </h3>
              <div className="space-y-2 text-xs font-mono">
                <a
                  href="https://github.com/Finnlayy/NIO/tree/main"
                  target="_blank"
                  rel="noreferrer"
                  className="p-3 rounded bg-slate-950 border border-slate-800 hover:border-slate-700 flex items-center justify-between transition-colors group block"
                >
                  <div>
                    <span className="font-bold text-slate-200 group-hover:text-amber-400 transition-colors">
                      Finnlayy/NIO (GitHub)
                    </span>
                    <p className="text-[11px] text-slate-400 mt-1">
                      Main branch repository reference
                    </p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-slate-400 group-hover:text-slate-100 transition-colors" />
                </a>

                <div className="p-3 rounded bg-slate-950 border border-slate-800">
                  <span className="font-bold text-slate-200">Sigma Alpha Matrix</span>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Multi-pair cointegration &amp; Ornstein-Uhlenbeck statistical dispersion
                  </p>
                  <span className="inline-block mt-2 text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                    ADAPTED INTO SWARM ENGINE
                  </span>
                </div>

                <div className="p-3 rounded bg-slate-950 border border-slate-800">
                  <span className="font-bold text-slate-200">Google Drive Blueprint</span>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Synchronized with live OAuth Drive API read tokens
                  </p>
                  <button
                    onClick={onOpenDriveModal}
                    className="mt-2 text-[11px] font-semibold text-blue-400 hover:text-blue-300 underline block"
                  >
                    Open Drive Explorer →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Section 2: Google Drive Files Explorer */}
      {activeSection === 'DRIVE_FILES' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-blue-400" />
                <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                  Discovered Drive Files ({driveFiles.length})
                </h3>
              </div>
              <button
                onClick={onOpenDriveModal}
                className="text-[11px] font-mono text-blue-400 hover:underline"
              >
                Search Drive
              </button>
            </div>

            {!driveConnected ? (
              <div className="p-6 text-center text-xs font-mono space-y-3">
                <p className="text-slate-400">
                  Google Drive is not currently authenticated. Connect your Google account to read blueprint documents directly.
                </p>
                <button
                  onClick={onOpenDriveModal}
                  className="px-3 py-1.5 rounded bg-blue-600 text-white font-semibold text-xs hover:bg-blue-500 transition-colors"
                >
                  Authenticate Google Drive
                </button>
              </div>
            ) : driveFiles.length === 0 ? (
              <div className="p-6 text-center text-xs font-mono text-slate-400">
                No matching blueprint files found yet. Click &quot;Search Drive&quot; to scan for OMEGA, NIO, or Sigma Alpha documents.
              </div>
            ) : (
              <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                {driveFiles.map((file) => (
                  <div
                    key={file.id}
                    onClick={() => onSelectDriveFile(file)}
                    className={`p-3 rounded border text-xs font-mono cursor-pointer transition-all ${
                      selectedFile?.id === file.id
                        ? 'bg-slate-800 border-amber-400/80 text-slate-100'
                        : 'bg-slate-950 border-slate-800 hover:border-slate-700 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold truncate max-w-[240px] text-slate-200">
                        {file.name}
                      </span>
                      {file.isBlueprintMatch && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300">
                          MATCH
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 mt-1">
                      <span>{file.mimeType.split('.').pop()}</span>
                      <span>{new Date(file.modifiedTime).toLocaleDateString()}</span>
                    </div>

                    {file.webViewLink && (
                      <a
                        href={file.webViewLink}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-[10px] text-blue-400 hover:underline flex items-center gap-1 mt-2"
                      >
                        <span>Open in Google Drive</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Drive File Content Viewer */}
          <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                  File Document Preview: {selectedFile?.name || 'None Selected'}
                </h3>
              </div>
            </div>

            {selectedFileContent ? (
              <div className="bg-slate-950 p-3 rounded border border-slate-800 max-h-[500px] overflow-y-auto">
                <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed">
                  {selectedFileContent}
                </pre>
              </div>
            ) : selectedFile ? (
              <div className="p-8 text-center text-xs font-mono text-slate-400">
                Loading document text from Google Drive API...
              </div>
            ) : (
              <div className="p-8 text-center text-xs font-mono text-slate-500">
                Select a file from the list to preview its contents and adapt blueprint logic
              </div>
            )}
          </div>
        </div>
      )}

      {/* Section 3: Mathematical Invariants */}
      {activeSection === 'MATH_FORMULAS' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {CANONICAL_BLUEPRINT_DOCS.mathFormulas.map((math) => (
            <div key={math.name} className="bg-slate-900 border border-slate-800 rounded-lg p-4">
              <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider mb-2">
                {math.name}
              </h3>
              <div className="bg-slate-950 p-3 rounded border border-slate-800 font-mono text-amber-400 text-sm font-bold text-center my-3">
                {math.formula}
              </div>
              <p className="text-xs text-slate-400 font-mono leading-relaxed">
                {math.description}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
