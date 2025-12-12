import React, { useState } from 'react';
import { ConfigForm } from './components/ConfigForm';
import { FileUpload } from './components/FileUpload';
import { AudioPlayer } from './components/AudioPlayer';
import { SystemStatus } from './components/SystemStatus';
import { DurationSelector } from './components/DurationSelector';
import { ChatInterface } from './components/ChatInterface';
import { Loader2, MessageSquare, Mic } from 'lucide-react';

type AppMode = 'chat' | 'podcast';

interface UploadedFile {
    id: string;
    name: string;
    size: number;
    type: string;
    status: 'uploading' | 'success' | 'error';
    docId?: string;
}

function App() {
    const [config, setConfig] = useState<any>({});
    const [files, setFiles] = useState<UploadedFile[]>([]);
    const [mode, setMode] = useState<AppMode>('podcast');
    const [duration, setDuration] = useState('5-10');
    const [promptType, setPromptType] = useState('default');
    const [isGenerating, setIsGenerating] = useState(false);
    const [result, setResult] = useState<{ audio_url: string; transcript: string } | null>(null);
    const [error, setError] = useState<string | null>(null);

    // 获取成功上传的文档ID列表
    const documentIds = files
        .filter(f => f.status === 'success' && f.docId)
        .map(f => f.docId!);

    const handleGenerate = async () => {
        if (documentIds.length === 0) {
            setError('请先上传文档');
            return;
        }
        if (!config.api_key) {
            setError('请配置 API Key');
            return;
        }

        setIsGenerating(true);
        setError(null);

        try {
            const response = await fetch('/api/podcast/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    document_ids: documentIds,
                    duration_range: duration,
                    prompt_type: promptType,
                    host_voice: 'alloy',
                    guest_voice: 'nova',
                    llm_provider: config.provider || 'openai',
                    llm_api_key: config.api_key,
                    llm_base_url: config.base_url || undefined,
                    llm_model: config.model_name || undefined,
                    tts_provider: 'openai',
                    tts_api_key: config.tts_api_key || config.api_key
                })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || '生成失败');
            }

            const data = await response.json();
            setResult({
                audio_url: data.audio_url,
                transcript: data.transcript
            });
        } catch (err: any) {
            setError(err.message || '生成过程中出现错误');
        } finally {
            setIsGenerating(false);
        }
    };

    return (
        <div className="h-screen p-4 flex flex-col font-mono text-slate-200 selection:bg-cyan-500/30 overflow-hidden">
            {/* Header */}
            <header className="mb-4 flex justify-between items-center border-b border-slate-700/50 pb-3 shrink-0">
                <div className="flex items-baseline">
                    <h1 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500 tracking-tighter uppercase drop-shadow-[0_0_15px_rgba(6,182,212,0.5)] mr-4">
                        NotebookLM <span className="text-slate-500">Lite</span>
                    </h1>
                    <p className="text-[10px] text-cyan-400/70 font-mono tracking-[0.2em] font-bold hidden sm:block">
                        V2.0 · RAG问答 + 播客生成
                    </p>
                </div>

                {/* 模式切换 */}
                <div className="flex items-center space-x-1 bg-slate-800/50 rounded-lg p-1">
                    <button
                        onClick={() => setMode('chat')}
                        className={`flex items-center px-3 py-1.5 rounded-md text-xs font-medium transition-all ${mode === 'chat'
                                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                                : 'text-slate-400 hover:text-slate-200'
                            }`}
                    >
                        <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
                        问答
                    </button>
                    <button
                        onClick={() => setMode('podcast')}
                        className={`flex items-center px-3 py-1.5 rounded-md text-xs font-medium transition-all ${mode === 'podcast'
                                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                                : 'text-slate-400 hover:text-slate-200'
                            }`}
                    >
                        <Mic className="w-3.5 h-3.5 mr-1.5" />
                        播客
                    </button>
                </div>
            </header>

            <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 max-w-[1800px] mx-auto w-full min-h-0">
                {/* 左侧：配置 + 文件上传 */}
                <div className="lg:col-span-3 space-y-4 flex flex-col h-full min-h-0">
                    <div className="flex-none">
                        <ConfigForm onConfigChange={setConfig} />
                    </div>
                    <div className="flex-1 min-h-0 overflow-hidden glass-panel rounded-xl p-4 border border-slate-700/50 bg-slate-900/50">
                        <FileUpload onFilesChange={setFiles} multiple={true} />
                    </div>
                </div>

                {/* 中间：主内容区 */}
                <div className="lg:col-span-6 flex flex-col h-full min-h-0">
                    <div className="glass-panel rounded-xl flex-1 flex flex-col relative group tech-border bg-slate-900/50 overflow-hidden">
                        {mode === 'chat' ? (
                            // RAG 问答模式
                            <ChatInterface
                                documentIds={documentIds}
                                llmConfig={{
                                    provider: config.provider || 'openai',
                                    api_key: config.api_key || '',
                                    base_url: config.base_url,
                                    model: config.model_name
                                }}
                            />
                        ) : (
                            // 播客生成模式
                            <div className="p-6 flex-1 flex flex-col">
                                <div className="mb-6">
                                    <DurationSelector value={duration} onChange={setDuration} />
                                </div>

                                <div className="mb-6">
                                    <label className="text-xs text-slate-400 font-medium uppercase tracking-wider block mb-2">
                                        播客风格
                                    </label>
                                    <select
                                        value={promptType}
                                        onChange={(e) => setPromptType(e.target.value)}
                                        className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                                    >
                                        <option value="default">采访对话</option>
                                        <option value="discussion">热烈讨论</option>
                                        <option value="teaching">教学讲解</option>
                                        <option value="argument">观点辩论</option>
                                        <option value="interview">模拟面试</option>
                                    </select>
                                </div>

                                <div className="flex-1 flex items-center justify-center">
                                    <div className="text-center">
                                        <div className="text-6xl mb-4">🎙️</div>
                                        <p className="text-slate-400 text-sm mb-2">
                                            已选择 {documentIds.length} 个文档
                                        </p>
                                        <p className="text-slate-500 text-xs">
                                            预计生成 {duration} 分钟播客
                                        </p>
                                    </div>
                                </div>

                                {error && (
                                    <div className="mb-4 bg-red-950/30 border border-red-500/30 text-red-400 px-4 py-2 rounded text-xs flex items-center">
                                        <span className="mr-2">⚠️</span> {error}
                                    </div>
                                )}

                                <button
                                    onClick={handleGenerate}
                                    disabled={isGenerating || documentIds.length === 0}
                                    className={`w-full py-3 px-6 rounded-lg font-bold text-sm uppercase tracking-[0.15em] transition-all duration-300 ${isGenerating || documentIds.length === 0
                                            ? 'bg-slate-800 text-slate-600 cursor-not-allowed border border-slate-700'
                                            : 'bg-cyan-950/50 text-cyan-400 border border-cyan-500/50 hover:bg-cyan-500 hover:text-slate-950 hover:shadow-[0_0_30px_rgba(6,182,212,0.4)]'
                                        }`}
                                >
                                    {isGenerating ? (
                                        <span className="flex items-center justify-center">
                                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                            生成中...
                                        </span>
                                    ) : (
                                        '🚀 生成播客'
                                    )}
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* 右侧：输出 */}
                <div className="lg:col-span-3 space-y-4 flex flex-col h-full min-h-0">
                    {result ? (
                        <div className="animate-in fade-in slide-in-from-right duration-500 h-full overflow-y-auto custom-scrollbar">
                            <AudioPlayer audioUrl={result.audio_url} transcript={result.transcript} />
                        </div>
                    ) : (
                        <div className="glass-panel rounded-xl p-6 h-full border border-slate-800/50 flex flex-col items-center justify-center text-slate-700 font-mono text-sm tech-border bg-slate-900/30">
                            <div className="w-10 h-10 rounded-full border border-slate-800 flex items-center justify-center mb-3 animate-pulse">
                                <div className="w-1.5 h-1.5 bg-slate-800 rounded-full" />
                            </div>
                            <p className="tracking-widest uppercase text-[10px]">等待生成结果</p>
                        </div>
                    )}
                    <div className="shrink-0">
                        <SystemStatus />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default App;
