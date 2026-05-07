import React, { useEffect, useRef, useState } from 'react';
import { BookmarkPlus, Send, Sparkles } from 'lucide-react';
import type { ApiConfig } from '../App';
import { translations, useLanguage } from '../App';
import { MarkdownView } from './MarkdownView';

interface Citation {
    source_id: string;
    source_title: string;
    chunk_id: string;
    score: number;
    excerpt: string;
}

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    citations?: Citation[];
}

interface ChatPanelProps {
    sourceIds: string[];
    config: ApiConfig;
    onSourceCreated?: () => void | Promise<void>;
    onNoteCreated?: () => void | Promise<void>;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ sourceIds, config, onSourceCreated, onNoteCreated }) => {
    const { lang } = useLanguage();
    const t = translations[lang];
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [notice, setNotice] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;
        if (sourceIds.length === 0) return alert(lang === 'zh' ? '请先选择来源' : 'Select sources first.');

        const userMessage: Message = { id: crypto.randomUUID(), role: 'user', content: input.trim() };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);
        setNotice('');
        const assistantId = crypto.randomUUID();

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: userMessage.content,
                    source_ids: sourceIds,
                    history: messages.map(m => ({ role: m.role, content: m.content })),
                    llm_provider: config.textProvider,
                    llm_api_key: config.textApiKey,
                    llm_base_url: config.textBaseUrl || undefined,
                    llm_model: config.textModel || undefined
                })
            });
            if (!response.ok) throw new Error(await response.text());
            if (!response.body) throw new Error('Streaming response is unavailable');
            setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }]);
            await readSseStream(response, event => {
                if (event.type === 'delta') {
                    setMessages(prev => prev.map(message => (
                        message.id === assistantId
                            ? { ...message, content: message.content + (event.payload.content || '') }
                            : message
                    )));
                }
                if (event.type === 'final') {
                    setMessages(prev => prev.map(message => (
                        message.id === assistantId
                            ? {
                                ...message,
                                content: event.payload.answer || message.content,
                                citations: event.payload.citations || []
                            }
                            : message
                    )));
                }
                if (event.type === 'error') {
                    throw new Error(event.payload.message || 'Stream failed');
                }
            });
        } catch {
            setMessages(prev => [...prev, {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: lang === 'zh' ? '请求失败，请检查模型配置或来源。' : 'Request failed. Check model settings or sources.'
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const saveAnswer = async (message: Message) => {
        const response = await fetch('/api/chat/save-answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: message.content.slice(0, 40) || 'Saved answer', answer: message.content, source_ids: sourceIds })
        });
        if (!response.ok) {
            setNotice(lang === 'zh' ? '保存失败' : 'Save failed');
            return;
        }
        await onSourceCreated?.();
        setNotice(lang === 'zh' ? '已保存为来源' : 'Saved as source');
    };

    const saveNote = async (message: Message) => {
        const response = await fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: message.content.split('\n').find(line => line.trim())?.replace(/^#+\s*/, '').slice(0, 40) || 'Chat note',
                body: message.content,
                source_ids: sourceIds,
                tags: ['chat']
            })
        });
        if (response.ok) {
            await onNoteCreated?.();
            setNotice(lang === 'zh' ? '已保存为笔记' : 'Saved as note');
        } else {
            setNotice(lang === 'zh' ? '保存失败' : 'Save failed');
        }
    };

    return (
        <>
            <div className="panel-header">
                <h2>{t.chat}</h2>
                <button onClick={() => setMessages([])} className="text-xs font-medium text-teal-700 bg-teal-50 px-3 py-1 rounded-full">
                    {lang === 'zh' ? '新对话' : 'New'}
                </button>
            </div>
            <div className="panel-body flex flex-col">
                {notice && <div className="chat-notice">{notice}</div>}
                <div className="flex-1 overflow-y-auto pb-4 space-y-4">
                    {messages.length === 0 && (
                        <div className="h-full flex flex-col items-center justify-center p-8 text-center">
                            <Sparkles className="w-12 h-12 text-teal-500 mb-3" />
                            <h3 className="text-2xl font-bold text-gray-700">{t.startChat}</h3>
                            <p className="text-sm text-gray-500 mt-2">{sourceIds.length} {lang === 'zh' ? '个来源已选择' : 'sources selected'}</p>
                        </div>
                    )}
                    {messages.map(message => (
                        <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`chat-bubble ${message.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'}`}>
                                {message.role === 'assistant' ? (
                                    <MarkdownView content={message.content} />
                                ) : (
                                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                                )}
                                {message.role === 'assistant' && (
                                    <div className="chat-actions">
                                        <button onClick={() => saveNote(message)} className="text-xs inline-flex items-center gap-1 text-teal-700">
                                            <BookmarkPlus size={13} /> {lang === 'zh' ? '保存为笔记' : 'Save as note'}
                                        </button>
                                        <button onClick={() => saveAnswer(message)} className="text-xs inline-flex items-center gap-1 text-teal-700">
                                            <BookmarkPlus size={13} /> {lang === 'zh' ? '保存为来源' : 'Save as source'}
                                        </button>
                                    </div>
                                )}
                                {message.citations && message.citations.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-gray-200 space-y-2">
                                        {message.citations.slice(0, 3).map(citation => (
                                            <div key={citation.chunk_id} className="text-[11px] bg-white/70 rounded-md p-2 text-gray-600">
                                                <div className="font-semibold text-gray-800">{citation.source_title || citation.source_id}</div>
                                                <div className="line-clamp-2">{citation.excerpt}</div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                    {isLoading && <div className="chat-bubble chat-bubble-ai w-fit">{lang === 'zh' ? '生成中...' : 'Thinking...'}</div>}
                    <div ref={messagesEndRef} />
                </div>
                <div className="pt-4 border-t border-gray-100">
                    <div className="relative">
                        <input
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendMessage())}
                            placeholder={t.inputPlaceholder}
                            className="w-full pl-5 pr-14 py-3 bg-white border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-teal-200"
                        />
                        <button onClick={sendMessage} disabled={!input.trim() || isLoading} className="absolute right-2 top-1.5 icon-btn primary">
                            <Send size={18} />
                        </button>
                    </div>
                </div>
            </div>
        </>
    );
};

const readSseStream = async (
    response: Response,
    onEvent: (event: { type: string; payload: any }) => void
) => {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
            const eventLine = part.split('\n').find(line => line.startsWith('event:'));
            const dataLine = part.split('\n').find(line => line.startsWith('data:'));
            if (!eventLine || !dataLine) continue;
            onEvent({
                type: eventLine.replace('event:', '').trim(),
                payload: JSON.parse(dataLine.replace('data:', '').trim())
            });
        }
    }
};
