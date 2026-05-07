import React, { useEffect, useState } from 'react';
import { FilePlus2, Loader2, NotebookPen, Plus, Search, Trash2 } from 'lucide-react';
import { useLanguage } from '../App';

interface NoteItem {
    id: string;
    title: string;
    body: string;
    source_ids: string[];
    tags: string[];
}

interface NotesPanelProps {
    selectedSourceIds: string[];
    onSourceCreated: () => Promise<void>;
    refreshKey?: number;
}

export const NotesPanel: React.FC<NotesPanelProps> = ({ selectedSourceIds, onSourceCreated, refreshKey = 0 }) => {
    const { lang } = useLanguage();
    const [notes, setNotes] = useState<NoteItem[]>([]);
    const [query, setQuery] = useState('');
    const [title, setTitle] = useState('');
    const [body, setBody] = useState('');
    const [busyId, setBusyId] = useState<string | null>(null);
    const [isCreating, setIsCreating] = useState(false);

    const refresh = async (search = query) => {
        const suffix = search.trim() ? `?query=${encodeURIComponent(search.trim())}` : '';
        const response = await fetch(`/api/notes${suffix}`);
        if (!response.ok) return;
        const payload = await response.json();
        setNotes(payload.notes || []);
    };

    useEffect(() => {
        refresh('');
    }, [refreshKey]);

    const createNote = async () => {
        if (!body.trim()) return;
        setIsCreating(true);
        try {
            const response = await fetch('/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: title.trim() || (lang === 'zh' ? '未命名笔记' : 'Untitled note'),
                    body,
                    source_ids: selectedSourceIds,
                    tags: []
                })
            });
            if (response.ok) {
                setTitle('');
                setBody('');
                await refresh('');
            }
        } finally {
            setIsCreating(false);
        }
    };

    const convertToSource = async (noteId: string) => {
        setBusyId(noteId);
        try {
            const response = await fetch(`/api/notes/${noteId}/source`, { method: 'POST' });
            if (response.ok) await onSourceCreated();
        } finally {
            setBusyId(null);
        }
    };

    const deleteNote = async (noteId: string) => {
        setBusyId(noteId);
        try {
            await fetch(`/api/notes/${noteId}`, { method: 'DELETE' });
            setNotes(prev => prev.filter(note => note.id !== noteId));
        } finally {
            setBusyId(null);
        }
    };

    return (
        <section className="notes-section">
            <div className="notes-head">
                <h2><NotebookPen size={17} /> {lang === 'zh' ? '笔记' : 'Notes'}</h2>
                <button className="icon-btn subtle" onClick={() => refresh(query)} title="Refresh">
                    <Search size={15} />
                </button>
            </div>
            <div className="notes-body">
                <input
                    value={query}
                    onChange={event => setQuery(event.target.value)}
                    onKeyDown={event => event.key === 'Enter' && refresh(query)}
                    placeholder={lang === 'zh' ? '搜索笔记...' : 'Search notes...'}
                    className="search-input mb-2"
                />
                <input
                    value={title}
                    onChange={event => setTitle(event.target.value)}
                    placeholder={lang === 'zh' ? '笔记标题' : 'Note title'}
                    className="search-input mb-2"
                />
                <textarea
                    value={body}
                    onChange={event => setBody(event.target.value)}
                    placeholder={lang === 'zh' ? '记录摘录、想法或整理结果' : 'Capture excerpts or ideas'}
                    className="search-input min-h-20 resize-none"
                />
                <button className="primary-btn compact w-full mt-2" disabled={!body.trim() || isCreating} onClick={createNote}>
                    {isCreating ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                    {lang === 'zh' ? '添加笔记' : 'Add Note'}
                </button>
                <div className="notes-list">
                    {notes.map(note => (
                        <article key={note.id} className="note-card">
                            <h3>{note.title}</h3>
                            <p>{note.body}</p>
                            <div className="note-actions">
                                <button className="secondary-btn compact" onClick={() => convertToSource(note.id)} disabled={busyId === note.id}>
                                    <FilePlus2 size={13} /> {lang === 'zh' ? '转来源' : 'To Source'}
                                </button>
                                <button className="icon-btn subtle" onClick={() => deleteNote(note.id)} disabled={busyId === note.id}>
                                    <Trash2 size={13} />
                                </button>
                            </div>
                        </article>
                    ))}
                </div>
            </div>
        </section>
    );
};
