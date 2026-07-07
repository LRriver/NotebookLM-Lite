/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import App, { LanguageContext } from '../App';
import { StudioPanel } from './StudioPanel';
import { SlideDeckWorkspace } from './SlideDeckWorkspace';

afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
});

const outline = {
    title: 'Deck Outline',
    design_style: 'warm technical',
    audience: 'engineers',
    slides: [{
        page: 1,
        title: 'Intro',
        narrative_goal: 'Introduce the material',
        key_points: ['Alpha'],
        visual_direction: 'Clean diagram'
    }]
};

const promptPlan = {
    slide_prompts: [{
        page: 1,
        title: 'Intro',
        content_summary: 'Alpha summary',
        display_content: 'Alpha display',
        prompt: 'Create an alpha slide'
    }]
};

const createdDeck = {
    id: 'deck_1',
    title: 'Slide Deck',
    source_ids: ['src_1'],
    source_snapshot: [{ source_id: 'src_1', title: 'Source One', excerpt: 'Alpha text' }],
    config_snapshot: { aspect_ratio: '16:9' },
    outline: null,
    prompt_plan: null,
    slides: [],
    status: 'draft',
    stage: 'created',
    error: null,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z'
};

function deckPatch(patch: Record<string, unknown>) {
    return { ...createdDeck, ...patch, updated_at: '2026-06-01T00:01:00Z' };
}

function renderWorkspace(props: Partial<React.ComponentProps<typeof SlideDeckWorkspace>> = {}) {
    return render(
        <LanguageContext.Provider value={{ lang: 'zh', setLang: vi.fn() }}>
            <SlideDeckWorkspace
                deckId="deck_1"
                sourceIds={['src_1']}
                onBack={vi.fn()}
                onArtifactGenerated={vi.fn()}
                {...props}
            />
        </LanguageContext.Provider>
    );
}

describe('SlideDeckWorkspace', () => {
    test('runs the two-confirmation slide deck workflow and exports PPTX', async () => {
        let currentDeck = deckPatch({ outline, stage: 'outline_ready' });
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            const method = init?.method || 'GET';
            if (url.startsWith('/api/slide-decks/jobs/')) return json({ id: 'job_status', deck_id: 'deck_1', stage: 'slide_generation', status: 'succeeded', progress: 1 });
            if (url === '/api/slide-decks/deck_1' && method === 'GET') return json(currentDeck);
            if (url.endsWith('/outline/jobs')) return json({ id: 'job_outline', deck_id: 'deck_1', stage: 'outline', status: 'succeeded', progress: 1 });
            if (url.endsWith('/outline') && method === 'PATCH') {
                currentDeck = deckPatch({ outline, stage: 'outline_confirmed' });
                return json(currentDeck);
            }
            if (url.endsWith('/prompt-plan/jobs')) {
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'prompt_plan_ready' });
                return json({ id: 'job_prompt', deck_id: 'deck_1', stage: 'prompt_plan', status: 'succeeded', progress: 1 });
            }
            if (url.endsWith('/prompt-plan') && method === 'PATCH') {
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'prompt_plan_confirmed' });
                return json(currentDeck);
            }
            if (url === '/api/slide-decks/deck_1/generate/jobs?background=true' && method === 'POST') {
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'slides_ready', status: 'ready', slides: [slide()] });
                return json({ id: 'job_slides', deck_id: 'deck_1', stage: 'slide_generation', status: 'succeeded', progress: 1 });
            }
            if (url.endsWith('/export/jobs')) return json({ id: 'job_export', deck_id: 'deck_1', stage: 'export', status: 'succeeded', progress: 1, result_ref: 'export_1' });
            if (url.endsWith('/regenerate')) {
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'slides_ready', status: 'ready', slides: [slide()] });
                return json(currentDeck);
            }
            if (url.endsWith('/edit')) {
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'slides_ready', status: 'ready', slides: [slide({ edit_history: [{ id: 'edit_1', instruction: '更亮', previous_asset_id: 'asset_1', next_asset_id: 'asset_2', created_at: '2026-06-01T00:02:00Z' }] })] });
                return json(currentDeck);
            }
            if (url === '/api/slide-decks' && method === 'POST') return json(createdDeck);
            currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'prompt_plan_ready' });
            return json(currentDeck);
        });
        vi.stubGlobal('fetch', fetchMock);

        renderWorkspace();

        expect(await screen.findByText('Slide Deck 工作区')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /生成大纲/ }));
        await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks/deck_1/outline/jobs', expect.objectContaining({ method: 'POST' })));
        fireEvent.click(await screen.findByRole('button', { name: /确认大纲/ }));
        fireEvent.click(await screen.findByRole('button', { name: /生成提示计划/ }));
        fireEvent.click(await screen.findByRole('button', { name: /确认提示计划/ }));
        fireEvent.click(await screen.findByRole('button', { name: /生成幻灯片/ }));
        expect((await screen.findAllByText('Intro')).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByAltText('Intro')).toHaveAttribute('src', '/api/slide-decks/deck_1/slides/slide_1/image');
        fireEvent.click(screen.getByRole('button', { name: /重新生成/ }));
        fireEvent.change(screen.getByPlaceholderText('描述这页要怎么改...'), { target: { value: '更亮' } });
        fireEvent.click(screen.getByRole('button', { name: /编辑当前页/ }));
        expect(await screen.findByText('更亮')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /导出 PPTX/ }));

        await waitFor(() => expect(screen.getByRole('link', { name: /下载 PPTX/ })).toHaveAttribute('href', '/api/slide-decks/deck_1/download?format=pptx'));
    });

    test('creates a deck from selected sources when no deck id is provided and returns to notebook', async () => {
        const onBack = vi.fn();
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            const method = init?.method || 'GET';
            if (url === '/api/slide-decks' && method === 'POST') return json(createdDeck);
            return json(createdDeck);
        });
        vi.stubGlobal('fetch', fetchMock);

        renderWorkspace({ deckId: null, sourceIds: ['src_1', 'src_2'], onBack });

        expect(await screen.findByText('Slide Deck 工作区')).toBeInTheDocument();
        expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks', expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('src_2')
        }));

        fireEvent.click(screen.getByRole('button', { name: /返回/ }));
        expect(onBack).toHaveBeenCalledTimes(1);
    });

    test('opens the slide deck workspace from the Studio PPT card', () => {
        const onOpenSlideDeck = vi.fn();

        render(
            <LanguageContext.Provider value={{ lang: 'zh', setLang: vi.fn() }}>
                <StudioPanel
                    sourceIds={['src_1']}
                    config={minimalConfig}
                    contents={[]}
                    onContentGenerated={vi.fn()}
                    onOpenSlideDeck={onOpenSlideDeck}
                />
            </LanguageContext.Provider>
        );

        fireEvent.click(screen.getByRole('button', { name: /PPT/ }));

        expect(onOpenSlideDeck).toHaveBeenCalledWith(null);
    });

    test('recovers the active slide deck workspace after refresh from local storage', async () => {
        localStorage.setItem('notebooklm-active-slide-deck', 'deck_1');
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url === '/api/sources') return json({ sources: [] });
            if (url === '/api/artifacts') return json({ artifacts: [] });
            if (url === '/api/config') return json({ models: {} });
            if (url === '/api/slide-decks/deck_1') return json(deckPatch({ outline, stage: 'outline_ready' }));
            return json({});
        });
        vi.stubGlobal('fetch', fetchMock);

        render(<App />);

        expect(await screen.findByText('Slide Deck 工作区')).toBeInTheDocument();
        expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks/deck_1', undefined);
    });

    test('surfaces mutation errors and disables confirmation while edited JSON is invalid', async () => {
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            const method = init?.method || 'GET';
            if (url === '/api/slide-decks/deck_1' && method === 'GET') return json(deckPatch({ outline, stage: 'outline_ready' }));
            if (url.endsWith('/outline') && method === 'PATCH') return { ok: false, text: async () => 'invalid outline' } as Response;
            return json(deckPatch({ outline, stage: 'outline_ready' }));
        });
        vi.stubGlobal('fetch', fetchMock);

        renderWorkspace();

        const outlineEditor = await screen.findByLabelText('大纲');
        fireEvent.change(outlineEditor, { target: { value: '{ invalid json' } });
        expect(screen.getByRole('button', { name: /确认大纲/ })).toBeDisabled();

        fireEvent.change(outlineEditor, { target: { value: JSON.stringify(outline) } });
        expect(screen.getByRole('button', { name: /确认大纲/ })).not.toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: /确认大纲/ }));

        expect(await screen.findByText('invalid outline')).toBeInTheDocument();
    });

    test('allows retrying slide generation after a partial failure is recovered from backend state', async () => {
        const failedDeck = deckPatch({
            outline,
            prompt_plan: promptPlan,
            stage: 'slides_generating',
            status: 'failed',
            slides: [slide({ status: 'failed', error: 'page failed' })],
            error: 'page failed'
        });
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            const method = init?.method || 'GET';
            if (url.startsWith('/api/slide-decks/jobs/')) return json({ id: 'job_status', deck_id: 'deck_1', stage: 'slide_generation', status: 'succeeded', progress: 1 });
            if (url === '/api/slide-decks/deck_1' && method === 'GET') return json(failedDeck);
            if (url === '/api/slide-decks/deck_1/generate/jobs?background=true' && method === 'POST') return json({ id: 'job_retry', deck_id: 'deck_1', stage: 'slide_generation', status: 'succeeded', progress: 1 });
            return json(failedDeck);
        });
        vi.stubGlobal('fetch', fetchMock);

        renderWorkspace();

        expect(await screen.findByText('page failed')).toBeInTheDocument();
        const generateButton = screen.getByRole('button', { name: /生成幻灯片/ });
        expect(generateButton).not.toBeDisabled();
        fireEvent.click(generateButton);

        await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks/deck_1/generate/jobs?background=true', expect.objectContaining({ method: 'POST' })));
    });

    test('uses background slide generation and polls job progress', async () => {
        let currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'prompt_plan_confirmed', status: 'planning' });
        let jobPollCount = 0;
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            const method = init?.method || 'GET';
            if (url === '/api/slide-decks/deck_1' && method === 'GET') return json(currentDeck);
            if (url === '/api/slide-decks/deck_1/generate/jobs?background=true' && method === 'POST') {
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'slides_generating', status: 'generating', slides: [slide({ status: 'generating', asset_id: null })] });
                return json({ id: 'job_slides', deck_id: 'deck_1', stage: 'slide_generation', status: 'running', progress: 0.5 });
            }
            if (url === '/api/slide-decks/jobs/job_slides') {
                jobPollCount += 1;
                if (jobPollCount === 1) return json({ id: 'job_slides', deck_id: 'deck_1', stage: 'slide_generation', status: 'running', progress: 0.5 });
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'slides_ready', status: 'ready', slides: [slide()] });
                return json({ id: 'job_slides', deck_id: 'deck_1', stage: 'slide_generation', status: 'succeeded', progress: 1 });
            }
            return json(currentDeck);
        });
        vi.stubGlobal('fetch', fetchMock);

        renderWorkspace();

        fireEvent.click(await screen.findByRole('button', { name: /生成幻灯片/ }));

        await screen.findByText('running');
        await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks/deck_1/generate/jobs?background=true', expect.objectContaining({ method: 'POST' })));
        await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks/jobs/job_slides', undefined));
    });

    test('does not allow a recovered ready deck to regenerate outline and rewind the workflow', async () => {
        const readyDeck = deckPatch({
            outline,
            prompt_plan: promptPlan,
            stage: 'slides_ready',
            status: 'ready',
            slides: [slide()]
        });
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            const method = init?.method || 'GET';
            if (url === '/api/slide-decks/deck_1' && method === 'GET') return json(readyDeck);
            return json(readyDeck);
        });
        vi.stubGlobal('fetch', fetchMock);

        renderWorkspace();

        expect(await screen.findByAltText('Intro')).toBeInTheDocument();
        const outlineButton = screen.getByRole('button', { name: /生成大纲/ });
        expect(outlineButton).toBeDisabled();
        fireEvent.click(outlineButton);
        expect(fetchMock).not.toHaveBeenCalledWith('/api/slide-decks/deck_1/outline/jobs', expect.objectContaining({ method: 'POST' }));
    });

    test('resumes polling when a recovered deck is still generating slides', async () => {
        let currentDeck = deckPatch({
            outline,
            prompt_plan: promptPlan,
            stage: 'slides_generating',
            status: 'generating',
            slides: [slide({ status: 'generating', asset_id: null })]
        });
        let jobPollCount = 0;
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            const method = init?.method || 'GET';
            if (url === '/api/slide-decks/deck_1' && method === 'GET') return json(currentDeck);
            if (url === '/api/slide-decks/deck_1/jobs') {
                return json({
                    jobs: [{ id: 'job_slides', deck_id: 'deck_1', stage: 'slide_generation', status: 'running', progress: 0.4 }],
                    total: 1
                });
            }
            if (url === '/api/slide-decks/jobs/job_slides') {
                jobPollCount += 1;
                if (jobPollCount === 1) return json({ id: 'job_slides', deck_id: 'deck_1', stage: 'slide_generation', status: 'running', progress: 0.4 });
                currentDeck = deckPatch({ outline, prompt_plan: promptPlan, stage: 'slides_ready', status: 'ready', slides: [slide()] });
                return json({ id: 'job_slides', deck_id: 'deck_1', stage: 'slide_generation', status: 'succeeded', progress: 1 });
            }
            return json(currentDeck);
        });
        vi.stubGlobal('fetch', fetchMock);

        renderWorkspace();

        expect(await screen.findByText('running')).toBeInTheDocument();
        await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks/deck_1/jobs', undefined));
        await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/slide-decks/jobs/job_slides', undefined));
        expect(await screen.findByAltText('Intro')).toHaveAttribute('src', '/api/slide-decks/deck_1/slides/slide_1/image');
    });
});

function slide(patch: Record<string, unknown> = {}) {
    return {
        id: 'slide_1',
        deck_id: 'deck_1',
        page_number: 1,
        title: 'Intro',
        prompt: 'Create an alpha slide',
        display_content: 'Alpha display',
        content_summary: 'Alpha summary',
        asset_id: 'asset_1',
        status: 'succeeded',
        error: null,
        edit_history: [],
        created_at: '2026-06-01T00:00:00Z',
        updated_at: '2026-06-01T00:00:00Z',
        ...patch
    };
}

function json(payload: unknown) {
    return {
        ok: true,
        json: async () => payload,
        text: async () => JSON.stringify(payload)
    } as Response;
}

const minimalConfig = {
    textProvider: 'litellm',
    textApiKey: '',
    textApiKeySet: false,
    textBaseUrl: '',
    textModel: '',
    textThinking: 'disabled',
    embeddingProvider: 'openai-compatible',
    embeddingApiKey: '',
    embeddingApiKeySet: false,
    embeddingBaseUrl: '',
    embeddingModel: '',
    rerankProvider: 'openai-compatible',
    rerankApiKey: '',
    rerankApiKeySet: false,
    rerankBaseUrl: '',
    rerankModel: '',
    speechProvider: 'openai-compatible',
    speechApiKey: '',
    speechApiKeySet: false,
    speechBaseUrl: '',
    speechModel: '',
    speechVoice: '',
    speechFormat: 'mp3',
    theme: 'light'
} as const;
