import React, { useState } from 'react';

interface ConfigFormProps {
    onConfigChange: (config: any) => void;
}

export const ConfigForm: React.FC<ConfigFormProps> = ({ onConfigChange }) => {
    const [config, setConfig] = useState({
        provider: 'openai',
        api_key: '',
        base_url: '',
        model_name: 'gpt-4o',
        tts_api_key: ''
    });

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        const newConfig = { ...config, [name]: value };
        setConfig(newConfig);
        onConfigChange(newConfig);
    };

    return (
        <div className="glass-panel rounded-xl p-4 border border-slate-700/50 bg-slate-900/80 tech-border">
            <div className="flex items-center mb-4 border-b border-slate-700 pb-3">
                <div className="w-6 h-6 rounded bg-cyan-500/20 flex items-center justify-center mr-2 text-cyan-400">
                    ⚙️
                </div>
                <h2 className="text-sm font-bold text-cyan-400 tracking-widest uppercase">配置</h2>
            </div>

            <div className="space-y-3">
                <div>
                    <label className="text-xs text-slate-400 mb-1 block">AI 提供商</label>
                    <div className="relative">
                        <select
                            name="provider"
                            value={config.provider}
                            onChange={handleChange}
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 appearance-none cursor-pointer focus:outline-none focus:border-cyan-500"
                        >
                            <option value="openai">OpenAI / 兼容接口</option>
                            <option value="google">Google GenAI</option>
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 text-xs">
                            ▼
                        </div>
                    </div>
                </div>

                <div>
                    <label className="text-xs text-slate-400 mb-1 block">模型名称</label>
                    <input
                        type="text"
                        name="model_name"
                        value={config.model_name}
                        onChange={handleChange}
                        placeholder={config.provider === 'google' ? 'gemini-pro' : 'gpt-4o'}
                        className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                    />
                </div>

                <div>
                    <label className="text-xs text-slate-400 mb-1 block">API Key</label>
                    <input
                        type="password"
                        name="api_key"
                        value={config.api_key}
                        onChange={handleChange}
                        placeholder="sk-..."
                        className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                    />
                </div>

                {config.provider === 'openai' && (
                    <div>
                        <label className="text-xs text-slate-400 mb-1 block">
                            Base URL <span className="text-slate-600">(可选)</span>
                        </label>
                        <input
                            type="text"
                            name="base_url"
                            value={config.base_url}
                            onChange={handleChange}
                            placeholder="https://api.openai.com/v1"
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                        />
                    </div>
                )}

                <div>
                    <label className="text-xs text-slate-400 mb-1 block">
                        TTS API Key <span className="text-slate-600">(可选，默认同上)</span>
                    </label>
                    <input
                        type="password"
                        name="tts_api_key"
                        value={config.tts_api_key}
                        onChange={handleChange}
                        placeholder="使用相同的 API Key"
                        className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                    />
                </div>
            </div>
        </div>
    );
};
