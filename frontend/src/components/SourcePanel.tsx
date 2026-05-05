import React, { useRef, useState } from 'react';
import { Check, FileText, Loader2, Plus, Search, Trash2, Upload } from 'lucide-react';
import type { SourceItem } from '../App';
import { translations, useLanguage } from '../App';

interface SourcePanelProps {
    sources: SourceItem[];
    selectedSourceIds: string[];
    onSourcesChange: (sources: SourceItem[]) => void;
    onSelectedSourceIdsChange: (ids: string[]) => void;
    onRefresh: () => Promise<void>;
}

const ACCEPT_STRING = '.pdf,.docx,.txt,.md,.html,.htm,.csv,.json,.yaml,.yml';

export const SourcePanel: React.FC<SourcePanelProps> = ({
    sources,
    selectedSourceIds,
    onSourcesChange,
    onSelectedSourceIdsChange,
    onRefresh
}) => {
    const { lang } = useLanguage();
    const t = translations[lang];
    const [searchQuery, setSearchQuery] = useState('');
    const [textTitle, setTextTitle] = useState('');
    const [textValue, setTextValue] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const toggleSource = (id: string) => {
        onSelectedSourceIdsChange(
            selectedSourceIds.includes(id)
                ? selectedSourceIds.filter(item => item !== id)
                : [...selectedSourceIds, id]
        );
    };

    const uploadFiles = async (fileList: FileList) => {
        setIsUploading(true);
        try {
            for (const file of Array.from(fileList)) {
                const formData = new FormData();
                formData.append('file', file);
                await fetch('/api/sources/upload', { method: 'POST', body: formData });
            }
            await onRefresh();
        } finally {
            setIsUploading(false);
        }
    };

    const addTextSource = async () => {
        if (!textValue.trim()) return;
        const response = await fetch('/api/sources/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: textTitle || 'Pasted text', text: textValue })
        });
        if (response.ok) {
            const source = await response.json();
            onSourcesChange([source, ...sources]);
            onSelectedSourceIdsChange([...selectedSourceIds, source.id]);
            setTextTitle('');
            setTextValue('');
        }
    };

    const deleteSource = async (id: string) => {
        await fetch(`/api/sources/${id}`, { method: 'DELETE' });
        onSourcesChange(sources.filter(source => source.id !== id));
        onSelectedSourceIdsChange(selectedSourceIds.filter(item => item !== id));
    };

    const filteredSources = sources.filter(source =>
        `${source.title} ${source.filename || ''}`.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <>
            <div className="panel-header">
                <h2>{t.sources}</h2>
                <button onClick={() => fileInputRef.current?.click()} className="icon-btn" title="Upload">
                    {isUploading ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
                </button>
            </div>
            <div className="panel-body">
                <div className="relative mb-4">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder={t.searchPlaceholder}
                        className="search-input pl-9"
                    />
                </div>

                <button className="upload-area w-full" onClick={() => fileInputRef.current?.click()}>
                    <Upload size={22} className="mx-auto mb-2 text-teal-600" />
                    <span className="text-sm font-medium text-gray-600">{t.dragDropText}</span>
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept={ACCEPT_STRING}
                    multiple
                    className="hidden"
                    onChange={e => e.target.files && uploadFiles(e.target.files)}
                />

                <div className="mt-4 p-3 rounded-lg bg-white border border-gray-100">
                    <input
                        value={textTitle}
                        onChange={e => setTextTitle(e.target.value)}
                        placeholder={lang === 'zh' ? '文本标题' : 'Text title'}
                        className="search-input mb-2"
                    />
                    <textarea
                        value={textValue}
                        onChange={e => setTextValue(e.target.value)}
                        placeholder={lang === 'zh' ? '粘贴文本作为来源' : 'Paste text as a source'}
                        className="search-input min-h-24 resize-none"
                    />
                    <button onClick={addTextSource} className="primary-btn mt-2 w-full">
                        {lang === 'zh' ? '添加文本来源' : 'Add Text Source'}
                    </button>
                </div>

                <div className="mt-4 space-y-2">
                    {filteredSources.map(source => {
                        const selected = selectedSourceIds.includes(source.id);
                        return (
                            <div key={source.id} className={`source-row ${selected ? 'selected' : ''}`}>
                                <button className="flex flex-1 items-center gap-3 min-w-0 text-left" onClick={() => toggleSource(source.id)}>
                                    <div className="source-icon">
                                        {selected ? <Check size={16} /> : <FileText size={16} />}
                                    </div>
                                    <div className="min-w-0">
                                        <div className="truncate text-sm font-semibold text-gray-800">{source.title}</div>
                                        <div className="text-[11px] text-gray-500">
                                            {source.status} · {source.chunk_count} chunks · {source.char_count} chars
                                        </div>
                                    </div>
                                </button>
                                <button onClick={() => deleteSource(source.id)} className="icon-btn subtle" title="Delete">
                                    <Trash2 size={15} />
                                </button>
                            </div>
                        );
                    })}
                </div>
            </div>
        </>
    );
};
