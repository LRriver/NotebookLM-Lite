import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Download, Edit3, FileText, Loader2, RefreshCw, Wand2 } from 'lucide-react';
import { translations, useLanguage, type GeneratedContent } from '../App';

interface SlideDeckWorkspaceProps {
    deckId: string | null;
    sourceIds: string[];
    onBack: () => void;
    onArtifactGenerated: (content: GeneratedContent) => void;
    onDeckReady?: (deckId: string) => void;
}

interface SlideDeck {
    id: string;
    title: string;
    source_ids: string[];
    source_snapshot: Array<Record<string, unknown>>;
    config_snapshot: Record<string, unknown>;
    outline: any | null;
    prompt_plan: any | null;
    slides: SlideRecord[];
    status: string;
    stage: string;
    error?: string | null;
    created_at: string;
    updated_at: string;
}

interface SlideRecord {
    id: string;
    page_number: number;
    title: string;
    prompt?: string;
    display_content?: string;
    content_summary?: string;
    asset_id?: string | null;
    status: string;
    error?: string | null;
    edit_history?: Array<{ id: string; instruction: string; created_at: string }>;
}

interface JobResponse {
    id: string;
    stage: string;
    status: string;
    progress: number;
    result_ref?: string | null;
    error?: string | null;
    created_at?: string;
    updated_at?: string;
}

interface JobListResponse {
    jobs: JobResponse[];
    total: number;
}

export const SlideDeckWorkspace: React.FC<SlideDeckWorkspaceProps> = ({ deckId, sourceIds, onBack, onArtifactGenerated, onDeckReady }) => {
    const { lang } = useLanguage();
    const t = translations[lang];
    const [deck, setDeck] = useState<SlideDeck | null>(null);
    const [selectedSlideId, setSelectedSlideId] = useState<string | null>(null);
    const [isBusy, setIsBusy] = useState(false);
    const [error, setError] = useState('');
    const [editInstruction, setEditInstruction] = useState('');
    const [downloadUrl, setDownloadUrl] = useState('');
    const [outlineValid, setOutlineValid] = useState(true);
    const [promptPlanValid, setPromptPlanValid] = useState(true);
    const [activeJob, setActiveJob] = useState<JobResponse | null>(null);
    const loadSeq = useRef(0);

    const selectedSlide = useMemo(() => {
        if (!deck?.slides?.length) return null;
        return deck.slides.find(slide => slide.id === selectedSlideId) || deck.slides[0];
    }, [deck, selectedSlideId]);

    useEffect(() => {
        const sequence = loadSeq.current + 1;
        loadSeq.current = sequence;
        let active = true;
        setDeck(null);
        setSelectedSlideId(null);
        setIsBusy(false);
        setActiveJob(null);
        setDownloadUrl('');
        setError('');
        const boot = async () => {
            try {
                if (deckId) {
                    const loaded = await requestJson<SlideDeck>(`/api/slide-decks/${deckId}`);
                    if (active && sequence === loadSeq.current) {
                        applyDeck(loaded);
                        await resumeRunningJob(loaded, sequence);
                    }
                    return;
                }
                if (sourceIds.length === 0) {
                    throw new Error(lang === 'zh' ? '请先选择来源' : 'Select sources first');
                }
                const created = await requestJson<SlideDeck>('/api/slide-decks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: lang === 'zh' ? 'Slide Deck' : 'Slide Deck',
                        source_ids: sourceIds,
                        config: { aspect_ratio: '16:9', page_count: 6 }
                    })
                });
                if (active && sequence === loadSeq.current) {
                    applyDeck(created);
                    onDeckReady?.(created.id);
                    publishDeckArtifact(created);
                }
            } catch (err: any) {
                if (active && sequence === loadSeq.current) setError(err.message || String(err));
            }
        };
        boot();
        return () => { active = false; };
    }, [deckId, sourceIds.join('|')]);

    const applyDeck = (nextDeck: SlideDeck) => {
        setDeck(nextDeck);
        setDownloadUrl(canDownloadPptx(nextDeck) ? `/api/slide-decks/${nextDeck.id}/download?format=pptx` : '');
        if (nextDeck.slides?.length) {
            setSelectedSlideId(prev => prev && nextDeck.slides.some(slide => slide.id === prev) ? prev : nextDeck.slides[0].id);
        }
    };

    const publishDeckArtifact = (nextDeck: SlideDeck) => {
        onArtifactGenerated({
            id: `slide-deck-${nextDeck.id}`,
            type: 'slide_deck',
            title: nextDeck.title,
            createdAt: new Date(nextDeck.created_at || Date.now()),
            payload: { deck_id: nextDeck.id, stage: nextDeck.stage, deck_status: nextDeck.status }
        });
    };

    const refreshDeck = async (targetDeckId = deck?.id, sequence = loadSeq.current) => {
        if (!targetDeckId) return;
        const latest = await requestJson<SlideDeck>(`/api/slide-decks/${targetDeckId}`);
        if (sequence === loadSeq.current) applyDeck(latest);
    };

    const resumeRunningJob = async (loadedDeck: SlideDeck, sequence = loadSeq.current) => {
        if (loadedDeck.stage !== 'slides_generating' || loadedDeck.status !== 'generating') return;
        try {
            const response = await requestJson<JobListResponse>(`/api/slide-decks/${loadedDeck.id}/jobs`);
            if (sequence !== loadSeq.current) return;
            const runningJob = response.jobs
                .filter(job => job.stage === 'slide_generation' && ['pending', 'running'].includes(job.status))
                .sort((left, right) => timestamp(right.created_at) - timestamp(left.created_at))[0];
            if (runningJob) {
                setActiveJob(runningJob);
                await pollJob(runningJob.id, loadedDeck.id, sequence);
            }
        } catch (err: any) {
            if (sequence === loadSeq.current) setError(err.message || String(err));
        }
    };

    const runJobAndRefresh = async (path: string) => {
        if (!deck) return null;
        const sequence = loadSeq.current;
        setIsBusy(true);
        setError('');
        try {
            const isSlideGeneration = path.endsWith('/generate/jobs');
            const jobPath = isSlideGeneration ? `${path}?background=true` : path;
            const job = await requestJson<JobResponse>(jobPath, { method: 'POST' });
            if (sequence !== loadSeq.current) return null;
            setActiveJob(job);
            if (job.status === 'failed') {
                setError(job.error || 'Job failed');
            }
            if (isSlideGeneration && deck.prompt_plan?.slide_prompts?.length) {
                applyDeck({
                    ...deck,
                    stage: 'slides_generating',
                    status: 'generating',
                    slides: deck.prompt_plan.slide_prompts.map((item: any, index: number) => ({
                        id: `pending_${item.page || index + 1}`,
                        page_number: item.page || index + 1,
                        title: item.title || `Slide ${index + 1}`,
                        prompt: item.prompt || '',
                        display_content: item.display_content || '',
                        content_summary: item.content_summary || '',
                        asset_id: null,
                        status: 'generating',
                        error: null,
                        edit_history: [],
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString()
                    }))
                });
            }
            if (job.id && isSlideGeneration) {
                await pollJob(job.id, deck.id, sequence);
            } else if (job.id) {
                try {
                    const latestJob = await requestJson<JobResponse>(`/api/slide-decks/jobs/${job.id}`);
                    if (sequence === loadSeq.current) setActiveJob(latestJob);
                } catch {
                    // Job endpoint is best-effort for progress display; deck state remains authoritative.
                }
            }
            await refreshDeck(deck.id, sequence);
            if (sequence !== loadSeq.current) return null;
            return job;
        } catch (err: any) {
            if (sequence === loadSeq.current) setError(err.message || String(err));
            return null;
        } finally {
            if (sequence === loadSeq.current) setIsBusy(false);
        }
    };

    const pollJob = async (jobId: string, targetDeckId = deck?.id, sequence = loadSeq.current) => {
        for (let attempt = 0; attempt < 120; attempt += 1) {
            const latest = await requestJson<JobResponse>(`/api/slide-decks/jobs/${jobId}`);
            if (sequence !== loadSeq.current) return latest;
            setActiveJob(latest);
            await refreshDeck(targetDeckId, sequence);
            if (latest.status !== 'running' && latest.status !== 'pending') {
                if (latest.status === 'failed') setError(latest.error || 'Job failed');
                return latest;
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        throw new Error('Slide generation timed out');
    };

    const confirmOutline = async () => {
        if (!deck?.outline) return;
        const sequence = loadSeq.current;
        setIsBusy(true);
        setError('');
        try {
            const nextDeck = await requestJson<SlideDeck>(`/api/slide-decks/${deck.id}/outline`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ outline: deck.outline, confirmed: true })
            });
            if (sequence === loadSeq.current) applyDeck(nextDeck);
        } catch (err: any) {
            if (sequence === loadSeq.current) setError(err.message || String(err));
        } finally {
            if (sequence === loadSeq.current) setIsBusy(false);
        }
    };

    const confirmPromptPlan = async () => {
        if (!deck?.prompt_plan) return;
        const sequence = loadSeq.current;
        setIsBusy(true);
        setError('');
        try {
            const nextDeck = await requestJson<SlideDeck>(`/api/slide-decks/${deck.id}/prompt-plan`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt_plan: deck.prompt_plan, confirmed: true })
            });
            if (sequence === loadSeq.current) applyDeck(nextDeck);
        } catch (err: any) {
            if (sequence === loadSeq.current) setError(err.message || String(err));
        } finally {
            if (sequence === loadSeq.current) setIsBusy(false);
        }
    };

    const regenerateSlide = async () => {
        if (!deck || !selectedSlide) return;
        const sequence = loadSeq.current;
        setIsBusy(true);
        setError('');
        try {
            const nextDeck = await requestJson<SlideDeck>(`/api/slide-decks/${deck.id}/slides/${selectedSlide.id}/regenerate`, { method: 'POST' });
            if (sequence === loadSeq.current) applyDeck(nextDeck);
        } catch (err: any) {
            if (sequence === loadSeq.current) setError(err.message || String(err));
        } finally {
            if (sequence === loadSeq.current) setIsBusy(false);
        }
    };

    const editSlide = async () => {
        if (!deck || !selectedSlide || !editInstruction.trim()) return;
        const sequence = loadSeq.current;
        setIsBusy(true);
        setError('');
        try {
            const nextDeck = await requestJson<SlideDeck>(`/api/slide-decks/${deck.id}/slides/${selectedSlide.id}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ instruction: editInstruction.trim() })
            });
            if (sequence === loadSeq.current) {
                applyDeck(nextDeck);
                setEditInstruction('');
            }
        } catch (err: any) {
            if (sequence === loadSeq.current) setError(err.message || String(err));
        } finally {
            if (sequence === loadSeq.current) setIsBusy(false);
        }
    };

    const exportPptx = async () => {
        if (!deck) return;
        const sequence = loadSeq.current;
        const job = await runJobAndRefresh(`/api/slide-decks/${deck.id}/export/jobs`);
        if (job?.status === 'succeeded' && sequence === loadSeq.current) {
            setDownloadUrl(`/api/slide-decks/${deck.id}/download?format=pptx`);
            publishDeckArtifact({ ...deck, stage: 'exported' });
        }
    };

    const canConfirmOutline = Boolean(deck?.outline && outlineValid && ['outline_ready', 'outline_confirmed'].includes(deck.stage));
    const canConfirmPromptPlan = Boolean(deck?.prompt_plan && promptPlanValid && ['prompt_plan_ready', 'prompt_plan_confirmed'].includes(deck.stage));
    const canGenerateSlides = Boolean(deck && (deck.stage === 'prompt_plan_confirmed' || (deck.stage === 'slides_generating' && deck.status === 'failed')));
    const canGenerateOutline = Boolean(deck && ['created', 'outline_ready', 'outline_confirmed'].includes(deck.stage));
    const canExportDeck = Boolean(deck && hasCompleteSlideImages(deck));
    const canEditSelectedSlide = Boolean(selectedSlide?.asset_id && selectedSlide.status === 'succeeded');

    return (
        <div className="slide-deck-workspace">
            <header className="slide-deck-topbar">
                <button className="secondary-btn" onClick={onBack}><ArrowLeft size={16} />{lang === 'zh' ? '返回' : 'Back'}</button>
                <div>
                    <h1>{lang === 'zh' ? 'Slide Deck 工作区' : 'Slide Deck Workspace'}</h1>
                    <p>{deck?.title || t.tools.ppt}</p>
                </div>
                <button className="primary-btn" onClick={exportPptx} disabled={!deck || isBusy || !canExportDeck}>
                    <Download size={16} />{lang === 'zh' ? '导出 PPTX' : 'Export PPTX'}
                </button>
                {downloadUrl && <a className="secondary-btn" href={downloadUrl}><Download size={16} />{lang === 'zh' ? '下载 PPTX' : 'Download PPTX'}</a>}
            </header>

            {error && <div className="slide-deck-error">{error}</div>}
            {activeJob && (
                <div className="slide-deck-job">
                    <span>{activeJob.stage}</span>
                    <strong>{activeJob.status}</strong>
                    <progress value={activeJob.progress} max={1} />
                </div>
            )}
            {!deck && !error && <div className="slide-deck-loading"><Loader2 className="animate-spin" size={18} />Loading</div>}

            {deck && (
                <main className="slide-deck-grid">
                    <aside className="slide-list-pane">
                        <h2>{lang === 'zh' ? '页面' : 'Pages'}</h2>
                        {deck.slides.length === 0 && <div className="empty-slide-list">{lang === 'zh' ? '生成幻灯片后显示页面' : 'Slides appear after generation'}</div>}
                        {deck.slides.map(slide => (
                            <button
                                key={slide.id}
                                className={`slide-thumb ${selectedSlide?.id === slide.id ? 'active' : ''}`}
                                onClick={() => setSelectedSlideId(slide.id)}
                            >
                                <span>{slide.page_number}</span>
                                <strong>{slide.title}</strong>
                                <small>{slide.status}</small>
                            </button>
                        ))}
                    </aside>

                    <section className="slide-preview-pane">
                        {selectedSlide ? (
                            <>
                                <div className="slide-canvas">
                                    {selectedSlide.asset_id ? (
                                        <img
                                            className="slide-image-preview"
                                            src={`/api/slide-decks/${deck.id}/slides/${selectedSlide.id}/image`}
                                            alt={selectedSlide.title}
                                        />
                                    ) : (
                                        <>
                                            <FileText size={36} />
                                            <h2>{selectedSlide.title}</h2>
                                            <p>{selectedSlide.display_content || selectedSlide.content_summary || selectedSlide.prompt}</p>
                                        </>
                                    )}
                                </div>
                                {selectedSlide.error && <div className="slide-deck-error">{selectedSlide.error}</div>}
                            </>
                        ) : (
                            <div className="slide-canvas empty">
                                <Wand2 size={38} />
                                <h2>{lang === 'zh' ? '从来源生成演示文稿' : 'Generate a deck from sources'}</h2>
                                <p>{lang === 'zh' ? '先生成大纲，再确认提示计划，最后生成页面。' : 'Generate an outline, confirm prompts, then render slides.'}</p>
                            </div>
                        )}
                    </section>

                    <aside className="slide-workflow-pane">
                        <section>
                            <h2>{lang === 'zh' ? '工作流' : 'Workflow'}</h2>
                            <button className="primary-btn w-full" disabled={!canGenerateOutline || isBusy} onClick={() => runJobAndRefresh(`/api/slide-decks/${deck.id}/outline/jobs`)}>
                                {isBusy ? <Loader2 className="animate-spin" size={16} /> : null}{lang === 'zh' ? '生成大纲' : 'Generate outline'}
                            </button>
                            <EditableJson title={lang === 'zh' ? '大纲' : 'Outline'} value={deck.outline} onValidChange={setOutlineValid} onChange={outline => applyDeck({ ...deck, outline })} />
                            <button className="secondary-btn w-full" disabled={!canConfirmOutline || isBusy} onClick={confirmOutline}>{lang === 'zh' ? '确认大纲' : 'Confirm outline'}</button>
                            <button className="primary-btn w-full" disabled={deck.stage !== 'outline_confirmed' || isBusy} onClick={() => runJobAndRefresh(`/api/slide-decks/${deck.id}/prompt-plan/jobs`)}>
                                {lang === 'zh' ? '生成提示计划' : 'Generate prompt plan'}
                            </button>
                            <EditableJson title={lang === 'zh' ? '提示计划' : 'Prompt plan'} value={deck.prompt_plan} onValidChange={setPromptPlanValid} onChange={prompt_plan => applyDeck({ ...deck, prompt_plan })} />
                            <button className="secondary-btn w-full" disabled={!canConfirmPromptPlan || isBusy} onClick={confirmPromptPlan}>{lang === 'zh' ? '确认提示计划' : 'Confirm prompt plan'}</button>
                            <button className="primary-btn w-full" disabled={!canGenerateSlides || isBusy} onClick={() => runJobAndRefresh(`/api/slide-decks/${deck.id}/generate/jobs`)}>
                                {lang === 'zh' ? '生成幻灯片' : 'Generate slides'}
                            </button>
                        </section>

                        <section>
                            <h2>{lang === 'zh' ? '当前页' : 'Current slide'}</h2>
                            <button className="secondary-btn w-full" disabled={!selectedSlide || isBusy} onClick={regenerateSlide}><RefreshCw size={16} />{lang === 'zh' ? '重新生成' : 'Regenerate'}</button>
                            <textarea
                                value={editInstruction}
                                onChange={event => setEditInstruction(event.target.value)}
                                placeholder={lang === 'zh' ? '描述这页要怎么改...' : 'Describe how to edit this slide...'}
                            />
                            <button className="secondary-btn w-full" disabled={!canEditSelectedSlide || isBusy || !editInstruction.trim()} onClick={editSlide}><Edit3 size={16} />{lang === 'zh' ? '编辑当前页' : 'Edit current slide'}</button>
                            {selectedSlide?.edit_history?.length ? (
                                <div className="edit-history">
                                    <h3>{lang === 'zh' ? '编辑历史' : 'Edit history'}</h3>
                                    {selectedSlide.edit_history.map(item => <div key={item.id}>{item.instruction}</div>)}
                                </div>
                            ) : null}
                        </section>
                    </aside>
                </main>
            )}
        </div>
    );
};

const EditableJson: React.FC<{
    title: string;
    value: any;
    onChange: (value: any) => void;
    onValidChange: (valid: boolean) => void;
}> = ({ title, value, onChange, onValidChange }) => {
    const [text, setText] = useState('');
    const textRef = useRef(text);

    useEffect(() => {
        textRef.current = text;
    }, [text]);

    useEffect(() => {
        try {
            if (value && JSON.stringify(value) === JSON.stringify(JSON.parse(textRef.current))) {
                return;
            }
        } catch {
            // Invalid editor text should be replaced when parent value changes.
        }
        setText(value ? JSON.stringify(value, null, 2) : '');
        onValidChange(true);
    }, [value]);

    if (!value) return null;

    return (
        <label className="json-editor">
            <span>{title}</span>
            <textarea
                value={text}
                onChange={event => {
                    const next = event.target.value;
                    textRef.current = next;
                    setText(next);
                    try {
                        onChange(JSON.parse(next));
                        onValidChange(true);
                    } catch {
                        onValidChange(false);
                    }
                }}
            />
        </label>
    );
};

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, init);
    if (!response.ok) {
        const contentType = response.headers?.get('content-type') || '';
        if (contentType.includes('application/json')) {
            try {
                const payload = await response.json();
                const detail = payload?.detail ?? payload?.message ?? payload;
                throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
            } catch (err) {
                if (err instanceof Error) throw err;
            }
        }
        const text = await response.text();
        throw new Error(text || `${response.status} ${response.statusText}`);
    }
    return response.json();
}

function timestamp(value?: string) {
    if (!value) return 0;
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? 0 : parsed;
}

function canDownloadPptx(deck: SlideDeck) {
    return deck.stage === 'exported' && hasCompleteSlideImages(deck);
}

function hasCompleteSlideImages(deck: SlideDeck) {
    return (
        (deck.status === 'ready' || deck.stage === 'exported')
        && deck.slides.length > 0
        && deck.slides.every(slide => slide.status === 'succeeded' && Boolean(slide.asset_id))
    );
}
