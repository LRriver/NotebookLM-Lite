import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Loader2 } from 'lucide-react';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    sources?: Array<{
        content: string;
        score: number;
    }>;
}

interface ChatInterfaceProps {
    documentIds: string[];
    llmConfig: {
        provider: string;
        api_key: string;
        base_url?: string;
        model?: string;
    };
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ documentIds, llmConfig }) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;
        if (!llmConfig.api_key) {
            alert('请先配置 API Key');
            return;
        }

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim()
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: userMessage.content,
                    document_ids: documentIds,
                    history: messages.map(m => ({
                        role: m.role,
                        content: m.content
                    })),
                    llm_provider: llmConfig.provider,
                    llm_api_key: llmConfig.api_key,
                    llm_base_url: llmConfig.base_url,
                    llm_model: llmConfig.model
                })
            });

            if (!response.ok) {
                throw new Error('请求失败');
            }

            const data = await response.json();

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.answer,
                sources: data.sources
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: '抱歉，处理请求时出现错误。请检查配置并重试。'
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* 消息区域 */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-slate-500">
                        <Bot className="w-12 h-12 mb-3 opacity-50" />
                        <p className="text-sm">基于已上传文档进行问答</p>
                        <p className="text-xs mt-1">输入问题开始对话</p>
                    </div>
                )}

                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div className={`flex max-w-[80%] ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${message.role === 'user'
                                    ? 'bg-cyan-500/20 text-cyan-400 ml-2'
                                    : 'bg-purple-500/20 text-purple-400 mr-2'
                                }`}>
                                {message.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                            </div>
                            <div className={`rounded-xl p-3 ${message.role === 'user'
                                    ? 'bg-cyan-500/10 border border-cyan-500/30'
                                    : 'bg-slate-800/50 border border-slate-700'
                                }`}>
                                <p className="text-sm text-slate-200 whitespace-pre-wrap">{message.content}</p>

                                {/* 引用来源 */}
                                {message.sources && message.sources.length > 0 && (
                                    <div className="mt-2 pt-2 border-t border-slate-700">
                                        <p className="text-xs text-slate-500 mb-1">参考来源:</p>
                                        {message.sources.slice(0, 2).map((source, idx) => (
                                            <p key={idx} className="text-xs text-slate-400 bg-slate-900/50 p-2 rounded mt-1">
                                                {source.content}
                                            </p>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex justify-start">
                        <div className="flex items-center bg-slate-800/50 border border-slate-700 rounded-xl p-3">
                            <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                            <span className="ml-2 text-sm text-slate-400">思考中...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* 输入区域 */}
            <div className="p-4 border-t border-slate-700">
                <div className="flex items-end space-x-2">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="输入问题..."
                        rows={1}
                        className="flex-1 resize-none bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                        style={{ minHeight: '40px', maxHeight: '120px' }}
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!input.trim() || isLoading}
                        className={`p-2 rounded-lg transition-colors ${input.trim() && !isLoading
                                ? 'bg-cyan-500 text-white hover:bg-cyan-400'
                                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
                            }`}
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
};
