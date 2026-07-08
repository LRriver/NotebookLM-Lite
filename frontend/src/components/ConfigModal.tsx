import React, { useState } from 'react';
import { Cpu, Database, Image, Key, Mic, PencilLine, Rows3, X } from 'lucide-react';
import type { ApiConfig } from '../App';
import { useLanguage } from '../App';

interface ConfigModalProps {
    config: ApiConfig;
    onConfigChange: (config: ApiConfig) => void | Promise<void>;
    onClose: () => void;
}

export const ConfigModal: React.FC<ConfigModalProps> = ({ config, onConfigChange, onClose }) => {
    const { lang } = useLanguage();
    const [localConfig, setLocalConfig] = useState<ApiConfig>(config);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const setValue = (key: keyof ApiConfig, value: string) => {
        setLocalConfig(prev => ({ ...prev, [key]: value } as ApiConfig));
    };

    const keyPlaceholder = (isConfigured: boolean, label: string) => {
        if (isConfigured) {
            return lang === 'zh' ? `${label} 已在 config.yaml 配置，留空保留` : `${label} configured in config.yaml; leave blank to keep it`;
        }
        return lang === 'zh' ? `${label} API key` : `${label} API key`;
    };

    const save = async () => {
        setSaving(true);
        setError('');
        try {
            await onConfigChange(localConfig);
            onClose();
        } catch (exc) {
            setError(exc instanceof Error ? exc.message : String(exc));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div className="config-modal rounded-lg w-full max-w-4xl shadow-xl overflow-hidden" onClick={e => e.stopPropagation()}>
                <div className="config-modal-head px-6 py-4 flex items-center justify-between">
                    <h2 className="text-xl font-bold">{lang === 'zh' ? '模型配置' : 'Model Settings'}</h2>
                    <button onClick={onClose} className="icon-btn"><X size={20} /></button>
                </div>
                <div className="p-6 grid md:grid-cols-2 gap-6 max-h-[72vh] overflow-y-auto">
                    <section className="space-y-3">
                        <div className="config-section-title"><Cpu size={19} /> {lang === 'zh' ? '文本模型' : 'Text Model'}</div>
                        <select value={localConfig.textProvider} onChange={e => setValue('textProvider', e.target.value)} className="search-input">
                            <option value="litellm">LiteLLM default</option>
                            <option value="openai">OpenAI compatible</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="gemini">Gemini / GenAI</option>
                        </select>
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input type="password" value={localConfig.textApiKey} onChange={e => setValue('textApiKey', e.target.value)} placeholder={keyPlaceholder(localConfig.textApiKeySet, 'Text')} className="search-input pl-9" />
                        </div>
                        <input value={localConfig.textModel} onChange={e => setValue('textModel', e.target.value)} placeholder="openai/gpt-4o, anthropic/claude..., gemini/..." className="search-input" />
                        <input value={localConfig.textBaseUrl} onChange={e => setValue('textBaseUrl', e.target.value)} placeholder="https://api.openai.com/v1" className="search-input" />
                        <select value={localConfig.textThinking} onChange={e => setValue('textThinking', e.target.value)} className="search-input">
                            <option value="enabled">thinking enabled</option>
                            <option value="disabled">thinking disabled</option>
                        </select>
                    </section>
                    <section className="space-y-3">
                        <div className="config-section-title"><Database size={19} /> {lang === 'zh' ? 'Embedding 模型' : 'Embedding Model'}</div>
                        <input value={localConfig.embeddingModel} onChange={e => setValue('embeddingModel', e.target.value)} placeholder="openai/text-embedding-3-small" className="search-input" />
                        <input value={localConfig.embeddingBaseUrl} onChange={e => setValue('embeddingBaseUrl', e.target.value)} placeholder="https://api.openai.com/v1" className="search-input" />
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input type="password" value={localConfig.embeddingApiKey} onChange={e => setValue('embeddingApiKey', e.target.value)} placeholder={keyPlaceholder(localConfig.embeddingApiKeySet, 'Embedding')} className="search-input pl-9" />
                        </div>
                    </section>
                    <section className="space-y-3">
                        <div className="config-section-title"><Rows3 size={19} /> {lang === 'zh' ? 'Rerank 模型' : 'Rerank Model'}</div>
                        <input value={localConfig.rerankModel} onChange={e => setValue('rerankModel', e.target.value)} placeholder="bge-reranker, jina-reranker..." className="search-input" />
                        <input value={localConfig.rerankBaseUrl} onChange={e => setValue('rerankBaseUrl', e.target.value)} placeholder="https://api.example.com/v1" className="search-input" />
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input type="password" value={localConfig.rerankApiKey} onChange={e => setValue('rerankApiKey', e.target.value)} placeholder={keyPlaceholder(localConfig.rerankApiKeySet, 'Rerank')} className="search-input pl-9" />
                        </div>
                    </section>
                    <section className="space-y-3">
                        <div className="config-section-title"><Mic size={19} /> {lang === 'zh' ? '语音模型' : 'Speech Model'}</div>
                        <input value={localConfig.speechModel} onChange={e => setValue('speechModel', e.target.value)} placeholder="fnlp/MOSS-TTSD-v0.5" className="search-input" />
                        <input value={localConfig.speechBaseUrl} onChange={e => setValue('speechBaseUrl', e.target.value)} placeholder="https://api.siliconflow.cn/v1" className="search-input" />
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input type="password" value={localConfig.speechApiKey} onChange={e => setValue('speechApiKey', e.target.value)} placeholder={keyPlaceholder(localConfig.speechApiKeySet, 'Speech')} className="search-input pl-9" />
                        </div>
                        <input value={localConfig.speechVoice} onChange={e => setValue('speechVoice', e.target.value)} placeholder="voice" className="search-input" />
                        <input value={localConfig.speechFormat} onChange={e => setValue('speechFormat', e.target.value)} placeholder="mp3" className="search-input" />
                    </section>
                    <section className="space-y-3">
                        <div className="config-section-title"><Image size={19} /> {lang === 'zh' ? '图片生成模型' : 'Image Model'}</div>
                        <input value={localConfig.imageModel} onChange={e => setValue('imageModel', e.target.value)} placeholder="Qwen/Qwen-Image, gpt-image-1..." className="search-input" />
                        <input value={localConfig.imageBaseUrl} onChange={e => setValue('imageBaseUrl', e.target.value)} placeholder="https://api.example.com/v1" className="search-input" />
                        <select value={localConfig.imageAdapter} onChange={e => setValue('imageAdapter', e.target.value)} className="search-input">
                            <option value="raw_chat_multimodal">raw chat multimodal</option>
                            <option value="openai_image">OpenAI images</option>
                            <option value="siliconflow_image">SiliconFlow images</option>
                        </select>
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input type="password" value={localConfig.imageApiKey} onChange={e => setValue('imageApiKey', e.target.value)} placeholder={keyPlaceholder(localConfig.imageApiKeySet, 'Image')} className="search-input pl-9" />
                        </div>
                    </section>
                    <section className="space-y-3">
                        <div className="config-section-title"><PencilLine size={19} /> {lang === 'zh' ? '图片编辑模型' : 'Image Edit Model'}</div>
                        <input value={localConfig.editModel} onChange={e => setValue('editModel', e.target.value)} placeholder="multimodal edit model" className="search-input" />
                        <input value={localConfig.editBaseUrl} onChange={e => setValue('editBaseUrl', e.target.value)} placeholder="https://api.example.com/v1" className="search-input" />
                        <select value={localConfig.editAdapter} onChange={e => setValue('editAdapter', e.target.value)} className="search-input">
                            <option value="raw_chat_multimodal">raw chat multimodal</option>
                            <option value="openai_chat">OpenAI-compatible chat</option>
                        </select>
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input type="password" value={localConfig.editApiKey} onChange={e => setValue('editApiKey', e.target.value)} placeholder={keyPlaceholder(localConfig.editApiKeySet, 'Edit')} className="search-input pl-9" />
                        </div>
                    </section>
                </div>
                <div className="config-modal-foot p-5 flex items-center justify-between gap-3">
                    <div className="text-xs text-red-600 truncate">{error}</div>
                    <div className="flex justify-end gap-3">
                    <button onClick={onClose} className="secondary-btn">{lang === 'zh' ? '取消' : 'Cancel'}</button>
                    <button onClick={save} disabled={saving} className="primary-btn">{saving ? (lang === 'zh' ? '保存中...' : 'Saving...') : (lang === 'zh' ? '保存并刷新' : 'Save & Refresh')}</button>
                    </div>
                </div>
            </div>
        </div>
    );
};
