import { expect, test } from '@playwright/test';

const source = {
    id: 'src-https',
    kind: 'file',
    title: 'notes.md',
    filename: 'notes.md',
    status: 'ready',
    chunk_count: 2,
    char_count: 120,
    created_at: '2026-06-01T00:00:00Z'
};

test('non-PPT workflow covers source upload, RAG chat, studio artifacts, and podcast script', async ({ page }) => {
    let sources: typeof source[] = [];
    let notes: Array<Record<string, unknown>> = [];
    let artifactCount = 0;

    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources/upload', route => {
        sources = [source];
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(source)
        });
    });
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources, total: sources.length })
    }));
    await page.route('**/api/chat/stream', route => route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: [
            'event: delta',
            'data: {"content":"## HTTPS 要点\\n\\n"}',
            '',
            'event: delta',
            'data: {"content":"1. TLS 加密\\n2. 证书验证"}',
            '',
            'event: final',
            `data: {"citations":[{"source_id":"${source.id}","source_title":"${source.title}","chunk_id":"src-https_chunk_1","score":1,"excerpt":"TLS 证书验证让 HTTPS 能确认服务器身份。"}]}`,
            '',
            ''
        ].join('\n')
    }));
    await page.route('**/api/notes**', route => {
        const method = route.request().method();
        if (method === 'GET') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ notes, total: notes.length })
            });
        }
        notes = [{
            id: 'note-1',
            title: 'HTTPS 笔记',
            body: 'TLS 证书验证让 HTTPS 能确认服务器身份。',
            source_ids: [source.id],
            tags: ['security'],
            created_at: '2026-06-01T00:00:00Z',
            updated_at: '2026-06-01T00:00:00Z'
        }];
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(notes[0])
        });
    });
    await page.route('**/api/artifacts/generate', async route => {
        const request = route.request();
        const payload = request.postDataJSON() as { artifact_type: string };
        artifactCount += 1;
        const title = `生成 ${payload.artifact_type}`;
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                id: `artifact-${artifactCount}`,
                artifact_type: payload.artifact_type,
                title,
                created_at: '2026-06-01T00:00:00Z',
                markdown: `# ${title}\n\n1. 第一项\n2. 第二项`,
                payload: { title }
            })
        });
    });
    await page.route('**/api/podcast/generate', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            transcript: '# 播客脚本\n\n1. 开场\n2. 深入讨论',
            audio_url: null
        })
    }));

    await page.goto('/');

    await page.locator('input[type="file"]').setInputFiles({
        name: 'notes.md',
        mimeType: 'text/markdown',
        buffer: Buffer.from('# HTTPS\nTLS 证书验证让 HTTPS 更安全。')
    });
    await expect(page.getByText('notes.md')).toBeVisible();
    await page.getByText('notes.md').click();
    await expect(page.getByText('1 个来源已选择')).toBeVisible();

    await page.getByPlaceholder('基于选中来源提问...').fill('HTTPS 为什么安全？');
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'HTTPS 要点' })).toBeVisible();
    await expect(page.getByRole('listitem').filter({ hasText: 'TLS 加密' })).toBeVisible();
    await expect(page.getByText('TLS 证书验证让 HTTPS 能确认服务器身份。')).toBeVisible();
    await page.getByRole('button', { name: /保存为笔记/ }).click();
    await expect(page.getByText('已保存为笔记')).toBeVisible();
    await expect(page.getByText('HTTPS 笔记')).toBeVisible();

    for (const { label, type } of [
        { label: '思维图谱', type: 'mind_map' },
        { label: 'FAQ', type: 'faq' },
        { label: '卡片', type: 'flashcards' },
        { label: '报告', type: 'report' },
        { label: '表格', type: 'data_table' }
    ]) {
        await page.getByRole('button', { name: new RegExp(label) }).click();
        await page.getByRole('button', { name: '生成', exact: true }).click();
        await expect(page.getByText(`生成 ${type}`)).toBeVisible();
    }

    await page.getByRole('button', { name: '播客' }).click();
    await page.getByRole('button', { name: '20-30' }).click();
    await page.getByRole('button', { name: '生成播客' }).click();
    await page.getByRole('button', { name: /播客脚本 podcast/ }).click();
    await expect(page.getByRole('heading', { name: '播客脚本' })).toBeVisible();
    await expect(page.getByRole('listitem').filter({ hasText: '深入讨论' })).toBeVisible();
});
