/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { LanguageContext, type ApiConfig, type GeneratedContent } from '../App';
import { ChatPanel } from './ChatPanel';
import { ArtifactViewer } from './ArtifactViewer';
import { MarkdownView } from './MarkdownView';
import { StudioPanel } from './StudioPanel';

Element.prototype.scrollIntoView = vi.fn();

afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
});

const config: ApiConfig = {
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
    imageProvider: 'openai-compatible',
    imageApiKey: '',
    imageApiKeySet: false,
    imageBaseUrl: '',
    imageModel: '',
    imageAdapter: 'raw_chat_multimodal',
    editProvider: 'openai-compatible',
    editApiKey: '',
    editApiKeySet: false,
    editBaseUrl: '',
    editModel: '',
    editAdapter: 'raw_chat_multimodal',
    theme: 'light'
};

function renderZh(ui: React.ReactElement) {
    return render(
        <LanguageContext.Provider value={{ lang: 'zh', setLang: vi.fn() }}>
            {ui}
        </LanguageContext.Provider>
    );
}

function streamResponse(events: string[]) {
    return {
        ok: true,
        body: new ReadableStream({
            start(controller) {
                controller.enqueue(new TextEncoder().encode(events.join('\n')));
                controller.close();
            }
        }),
        text: async () => ''
    };
}

describe('Markdown rendering', () => {
    test('renders assistant markdown answers as rich content', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ...streamResponse([
                'event: delta',
                'data: {"content":"## HTTPS 要点\\n\\n- **加密传输**\\n- 证书验证"}',
                '',
                'event: final',
                'data: {"answer":"## HTTPS 要点\\n\\n- **加密传输**\\n- 证书验证","citations":[]}',
                '',
                ''
            ])
        }));

        renderZh(<ChatPanel sourceIds={['src-1']} config={config} onSourceCreated={vi.fn()} onNoteCreated={vi.fn()} />);

        fireEvent.change(screen.getByPlaceholderText('基于选中来源提问...'), {
            target: { value: 'HTTPS 为什么安全？' }
        });
        fireEvent.click(screen.getByRole('button', { name: '' }));

        expect(await screen.findByRole('heading', { name: 'HTTPS 要点' })).toBeInTheDocument();
        expect(screen.getByText('加密传输').tagName.toLowerCase()).toBe('strong');
        expect(screen.getByText('证书验证').closest('li')).toBeInTheDocument();

        await waitFor(() => {
            expect(globalThis.fetch).toHaveBeenCalled();
        });
    });

    test('refreshes notes after saving an answer as a note and only confirms successful saves', async () => {
        const onNoteCreated = vi.fn();
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(streamResponse([
                'event: delta',
                'data: {"content":"回答内容"}',
                '',
                'event: final',
                'data: {"answer":"回答内容","citations":[]}',
                '',
                ''
            ]))
            .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'note-1' }), text: async () => '' });
        vi.stubGlobal('fetch', fetchMock);

        renderZh(<ChatPanel sourceIds={['src-1']} config={config} onSourceCreated={vi.fn()} onNoteCreated={onNoteCreated} />);

        fireEvent.change(screen.getByPlaceholderText('基于选中来源提问...'), {
            target: { value: '总结一下' }
        });
        fireEvent.click(screen.getByRole('button', { name: '' }));
        await screen.findByText('回答内容');
        fireEvent.click(screen.getByRole('button', { name: /保存为笔记/ }));

        await waitFor(() => expect(onNoteCreated).toHaveBeenCalledTimes(1));
        expect(await screen.findByText('已保存为笔记')).toBeInTheDocument();
    });

    test('does not show a successful source-save notice when save-answer fails', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(streamResponse([
                'event: delta',
                'data: {"content":"回答内容"}',
                '',
                'event: final',
                'data: {"answer":"回答内容","citations":[]}',
                '',
                ''
            ]))
            .mockResolvedValueOnce({ ok: false, text: async () => 'save failed' });
        vi.stubGlobal('fetch', fetchMock);

        renderZh(<ChatPanel sourceIds={['src-1']} config={config} onSourceCreated={vi.fn()} onNoteCreated={vi.fn()} />);

        fireEvent.change(screen.getByPlaceholderText('基于选中来源提问...'), {
            target: { value: '总结一下' }
        });
        fireEvent.click(screen.getByRole('button', { name: '' }));
        await screen.findByText('回答内容');
        fireEvent.click(screen.getByRole('button', { name: /保存为来源/ }));

        await waitFor(() => expect(screen.queryByText('已保存为来源')).not.toBeInTheDocument());
        expect(await screen.findByText('保存失败')).toBeInTheDocument();
    });

    test('refreshes sources after saving an answer as a source', async () => {
        const onSourceCreated = vi.fn();
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(streamResponse([
                'event: delta',
                'data: {"content":"回答内容"}',
                '',
                'event: final',
                'data: {"answer":"回答内容","citations":[]}',
                '',
                ''
            ]))
            .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'src-saved' }), text: async () => '' });
        vi.stubGlobal('fetch', fetchMock);

        renderZh(<ChatPanel sourceIds={['src-1']} config={config} onSourceCreated={onSourceCreated} onNoteCreated={vi.fn()} />);

        fireEvent.change(screen.getByPlaceholderText('基于选中来源提问...'), {
            target: { value: '总结一下' }
        });
        fireEvent.click(screen.getByRole('button', { name: '' }));
        await screen.findByText('回答内容');
        fireEvent.click(screen.getByRole('button', { name: /保存为来源/ }));

        await waitFor(() => expect(onSourceCreated).toHaveBeenCalledTimes(1));
        expect(await screen.findByText('已保存为来源')).toBeInTheDocument();
    });

    test('renders quiz-only artifacts as an interactive quiz', () => {
        renderZh(
            <ArtifactViewer
                content={{
                    id: 'quiz-1',
                    type: 'quiz',
                    title: 'Quiz only',
                    createdAt: new Date(),
                    markdown: '# Quiz only',
                    payload: {
                        title: 'Quiz only',
                        cards: [],
                        quiz: [{
                            question: 'HTTPS 使用什么协议？',
                            options: ['TLS', 'FTP'],
                            answer: 'TLS',
                            explanation: 'HTTPS 使用 TLS。'
                        }]
                    }
                }}
            />
        );

        fireEvent.click(screen.getByRole('button', { name: 'TLS' }));

        expect(screen.getByText('回答正确')).toBeInTheDocument();
        expect(screen.getByText('得分 1 / 1')).toBeInTheDocument();
    });

    test('renders infographic SVG through an image URL instead of inline SVG markup', () => {
        const objectUrl = 'blob:infographic';
        const createObjectURL = vi.fn(() => objectUrl);
        const revokeObjectURL = vi.fn();
        vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });

        renderZh(
            <ArtifactViewer
                content={{
                    id: 'info-1',
                    type: 'infographic',
                    title: 'Info',
                    createdAt: new Date(),
                    payload: {
                        title: 'Info',
                        subtitle: '摘要',
                        svg: '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(2)</script><text>Info</text></svg>'
                    }
                }}
            />
        );

        expect(screen.getByAltText('Info')).toHaveAttribute('src', objectUrl);
        expect(document.querySelector('.infographic-frame svg')).not.toBeInTheDocument();
        expect(createObjectURL).toHaveBeenCalled();
    });

    test('renders studio artifact markdown tables instead of plain preformatted text', () => {
        const contents: GeneratedContent[] = [
            {
                id: 'artifact-1',
                type: 'report',
                title: 'Generated Artifact',
                createdAt: new Date('2026-06-01T00:00:00Z'),
                markdown: '## Rendered Report\n\n| 项目 | 说明 |\n| --- | --- |\n| HTTP | 明文传输 |',
                downloadMarkdownUrl: '/download.md',
                downloadJsonUrl: '/download.json'
            }
        ];

        renderZh(
            <StudioPanel
                sourceIds={['src-1']}
                config={config}
                contents={contents}
                onContentGenerated={vi.fn()}
                onOpenSlideDeck={vi.fn()}
            />
        );

        fireEvent.click(screen.getByRole('button', { name: 'Generated Artifact report' }));

        expect(screen.getByRole('heading', { name: 'Rendered Report' })).toBeInTheDocument();
        expect(screen.getByRole('cell', { name: 'HTTP' })).toBeInTheDocument();
        expect(screen.queryByText('## Rendered Report')).not.toBeInTheDocument();
    });

    test('renders ordered lists as list items', () => {
        const { container } = render(<MarkdownView content={'## 步骤\n\n1. 上传文件\n2. 选择来源\n3. 生成思维图谱'} />);
        const view = container.querySelector('.markdown-view') as HTMLElement;

        const items = within(view).getAllByRole('listitem');
        expect(items.map(item => item.textContent)).toEqual(['上传文件', '选择来源', '生成思维图谱']);
        expect(within(view).getByRole('list')).toBeInTheDocument();
    });
});
