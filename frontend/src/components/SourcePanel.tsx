import React, { useRef, useState } from 'react';
import { Upload, X, Plus, Search, CheckCircle2, Loader2 } from 'lucide-react';
import type { UploadedFile } from '../App';
import { useLanguage, translations } from '../App';

interface SourcePanelProps {
    files: UploadedFile[];
    onFilesChange: (files: UploadedFile[]) => void;
}

const ACCEPT_STRING = '.pdf,.docx,.txt,.md,.html,.htm';

const getFileIcon = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return '📄';
    if (ext === 'docx' || ext === 'doc') return '📘';
    if (ext === 'txt') return '📝';
    if (ext === 'md') return '📑';
    if (ext === 'html' || ext === 'htm') return '🌐';
    return '📄';
};

export const SourcePanel: React.FC<SourcePanelProps> = ({ files, onFilesChange }) => {
    const { lang } = useLanguage();
    const t = translations[lang];

    const [isDragging, setIsDragging] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    const isSupported = (file: File): boolean => {
        const ext = file.name.split('.').pop()?.toLowerCase();
        return ['pdf', 'docx', 'txt', 'md', 'html', 'htm'].includes(ext || '');
    };

    const uploadFile = async (file: File): Promise<UploadedFile> => {
        const tempId = Math.random().toString(36).substr(2, 9);
        const uploadedFile: UploadedFile = {
            id: tempId,
            name: file.name,
            size: file.size,
            type: file.type,
            status: 'uploading'
        };

        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch('/api/documents/upload', { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload failed');
            const data = await response.json();
            return { ...uploadedFile, status: 'success', docId: data.id };
        } catch {
            return { ...uploadedFile, status: 'error' };
        }
    };

    const handleFiles = async (fileList: FileList) => {
        const validFiles = Array.from(fileList).filter(isSupported);
        if (validFiles.length === 0) {
            alert('Please select supported files: PDF, DOCX, TXT, MD, HTML');
            return;
        }

        const placeholders: UploadedFile[] = validFiles.map(f => ({
            id: Math.random().toString(36).substr(2, 9),
            name: f.name,
            size: f.size,
            type: f.type,
            status: 'uploading' as const
        }));

        onFilesChange([...files, ...placeholders]);
        const results = await Promise.all(validFiles.map(uploadFile));
        onFilesChange([...files, ...results]);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files?.length > 0) handleFiles(e.dataTransfer.files);
    };

    const filteredFiles = files.filter(f =>
        f.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <>
            <div className="panel-header">
                <h2>{t.sources}</h2>
                <button onClick={() => fileInputRef.current?.click()} className="p-1.5 rounded-lg hover:bg-orange-50 text-orange-600 transition-colors">
                    <Plus size={18} />
                </button>
            </div>

            <div className="panel-body">
                {/* Search */}
                <div className="relative mb-4 group">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-orange-500 transition-colors" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder={t.searchPlaceholder}
                        className="w-full bg-white/80 backdrop-blur-sm border border-orange-100/50 rounded-xl py-3 pl-10 pr-4 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-200 focus:border-orange-300 transition-all placeholder:text-gray-400"
                    />
                </div>

                {/* Upload Zone */}
                <div
                    className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all gap-3 shadow-sm ${isDragging
                        ? 'border-orange-400 bg-orange-50'
                        : 'border-orange-300/40 bg-[#FFFDF9]/60 hover:bg-orange-50/80 hover:border-orange-300'}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                >
                    <div className="w-12 h-12 bg-white rounded-full shadow-md flex items-center justify-center text-orange-500 group-hover:scale-110 transition-transform">
                        <Upload size={24} />
                    </div>
                    <p className="text-sm font-medium text-gray-600 whitespace-pre-line">{t.dragDropText}</p>
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={(e) => e.target.files && handleFiles(e.target.files)}
                        accept={ACCEPT_STRING}
                        multiple
                        className="hidden"
                    />
                </div>

                {/* File List */}
                <div className="mt-4 space-y-3">
                    {files.length === 0 && (
                        <div className="text-center py-6">
                            <p className="text-sm text-gray-400">{lang === 'zh' ? '暂无来源' : 'No sources yet'}</p>
                        </div>
                    )}

                    {filteredFiles.map((file) => (
                        <div key={file.id} className={`group relative bg-white/90 backdrop-blur-sm p-3 rounded-xl border transition-all cursor-pointer flex items-center gap-3 ${file.status === 'success' ? 'border-orange-200 shadow-sm' : 'border-transparent hover:border-gray-200'}`}>
                            <div className="w-11 h-11 bg-orange-50 rounded-lg flex flex-col items-center justify-center shadow-inner shrink-0">
                                <span className="text-xl">{getFileIcon(file.name)}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="font-semibold text-[13px] text-gray-800 truncate">{file.name}</div>
                                <div className="flex items-center gap-2 text-[11px] text-gray-400 mt-0.5 font-medium">
                                    <span>{(file.size / 1024).toFixed(1)} KB</span>
                                    {file.status === 'uploading' && <Loader2 size={10} className="animate-spin text-orange-500" />}
                                    {file.status === 'error' && <span className="text-red-500">Error</span>}
                                </div>
                            </div>
                            {file.status === 'success' && (
                                <div className="w-5 h-5 bg-orange-500 rounded-full flex items-center justify-center shadow-md">
                                    <CheckCircle2 size={12} className="text-white" />
                                </div>
                            )}
                            <button
                                onClick={(e) => { e.stopPropagation(); onFilesChange(files.filter(f => f.id !== file.id)); }}
                                className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <X size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
};
