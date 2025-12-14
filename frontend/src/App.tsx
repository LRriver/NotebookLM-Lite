import React, { useState } from 'react';
import { SourcePanel } from './components/SourcePanel';
import { ChatPanel } from './components/ChatPanel';
import { StudioPanel } from './components/StudioPanel';
import { ConfigModal } from './components/ConfigModal';
import { Settings, Sparkles } from 'lucide-react';

export interface ApiConfig {
    textProvider: 'openai' | 'google';
    textApiKey: string;
    textBaseUrl: string;
    textModel: string;
    speechProvider: 'openai' | 'dashscope';
    speechApiKey: string;
    speechBaseUrl: string;
}

export interface UploadedFile {
    id: string;
    name: string;
    size: number;
    type: string;
    status: 'uploading' | 'success' | 'error';
    docId?: string;
}

export interface GeneratedContent {
    id: string;
    type: 'podcast' | 'ppt' | 'summary';
    title: string;
    createdAt: Date;
    audioUrl?: string;
    transcript?: string;
}

function App() {
    const [files, setFiles] = useState<UploadedFile[]>([]);
    const [generatedContents, setGeneratedContents] = useState<GeneratedContent[]>([]);
    const [showConfig, setShowConfig] = useState(false);
    const [config, setConfig] = useState<ApiConfig>({
        textProvider: 'openai',
        textApiKey: '',
        textBaseUrl: '',
        textModel: 'gpt-4o',
        speechProvider: 'openai',
        speechApiKey: '',
        speechBaseUrl: ''
    });

    // 获取成功上传的文档ID列表
    const documentIds = files
        .filter(f => f.status === 'success' && f.docId)
        .map(f => f.docId!);

    const handlePodcastGenerated = (content: GeneratedContent) => {
        setGeneratedContents(prev => [content, ...prev]);
    };

    return (
        <div className="h-screen flex flex-col bg-[var(--bg-primary)]">
            {/* Header */}
            <header className="flex items-center justify-between px-6 py-3 border-b border-[var(--border-light)] bg-white">
                <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-lg shadow-orange-200">
                        <Sparkles className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent">
                            NotebookLM Lite
                        </h1>
                        <p className="text-xs text-[var(--warm-500)]">智能文档助手</p>
                    </div>
                </div>

                <button
                    onClick={() => setShowConfig(true)}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border-light)] hover:bg-[var(--bg-hover)] transition-colors"
                >
                    <Settings className="w-4 h-4 text-[var(--warm-500)]" />
                    <span className="text-sm text-[var(--warm-600)]">设置</span>
                </button>
            </header>

            {/* Main Content - Three Column Layout */}
            <div className="flex-1 flex overflow-hidden">
                {/* Left Panel - Sources */}
                <div className="w-72 border-r border-[var(--border-light)] bg-white flex flex-col">
                    <SourcePanel
                        files={files}
                        onFilesChange={setFiles}
                    />
                </div>

                {/* Center Panel - Chat */}
                <div className="flex-1 flex flex-col bg-[var(--bg-primary)]">
                    <ChatPanel
                        documentIds={documentIds}
                        config={config}
                    />
                </div>

                {/* Right Panel - Studio */}
                <div className="w-80 border-l border-[var(--border-light)] bg-white flex flex-col">
                    <StudioPanel
                        documentIds={documentIds}
                        config={config}
                        contents={generatedContents}
                        onContentGenerated={handlePodcastGenerated}
                    />
                </div>
            </div>

            {/* Config Modal */}
            {showConfig && (
                <ConfigModal
                    config={config}
                    onConfigChange={setConfig}
                    onClose={() => setShowConfig(false)}
                />
            )}
        </div>
    );
}

export default App;
