document.addEventListener('DOMContentLoaded', () => {
  const list = document.getElementById('radar-list');
  const status = document.getElementById('radar-status');
  const filters = document.getElementById('radar-filters');
  if (!list || !status || !filters) return;

  let payload = null;
  let activeKeyword = 'All';

  const cleanMarkupText = (value) => {
    let text = String(value || '');
    // Some publisher metadata contains tags like <scp>NFM</scp>, and some feeds
    // HTML-encode those tags. Decode twice defensively, then return plain text.
    for (let i = 0; i < 2; i += 1) {
      const parsed = new DOMParser().parseFromString(text, 'text/html');
      const next = parsed.body.textContent || '';
      if (next === text) break;
      text = next;
    }
    return text.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  };

  const parseDateOnly = (value) => {
    if (!value) return null;
    const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return null;
    return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  };

  const formatDateOnly = (value) => {
    const date = parseDateOnly(value);
    if (!date) return value || 'Unknown date';
    return new Intl.DateTimeFormat('en', {
      timeZone: 'UTC',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    }).format(date);
  };

  const formatUpdatedAt = (value) => {
    if (!value) return 'Awaiting first verified sync';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Updated daily';
    return `Updated ${new Intl.DateTimeFormat('en', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date)}`;
  };

  const dateRange = () => {
    const end = parseDateOnly(payload?.targetDate);
    const days = Number(payload?.windowDays) || 30;
    if (!end) return [];
    const values = [];
    for (let i = 0; i < days; i += 1) {
      const current = new Date(end);
      current.setUTCDate(end.getUTCDate() - i);
      values.push(current.toISOString().slice(0, 10));
    }
    return values;
  };

  const renderFilters = () => {
    filters.replaceChildren();
    const keywords = ['All', ...(payload?.keywords || [])];
    keywords.forEach(keyword => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `radar-filter${keyword === activeKeyword ? ' is-active' : ''}`;
      button.textContent = keyword;
      button.setAttribute('aria-pressed', keyword === activeKeyword ? 'true' : 'false');
      button.addEventListener('click', () => {
        activeKeyword = keyword;
        renderFilters();
        renderPapers();
      });
      filters.appendChild(button);
    });
  };

  const createTag = (keyword) => {
    const tag = document.createElement('span');
    tag.className = 'radar-tag';
    tag.textContent = cleanMarkupText(keyword);
    return tag;
  };

  const parseGuidePoints = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return [];
    const allowedLabels = new Set([
      '新在哪里',
      '有意思的现象',
      '怎么解释',
      '为什么重要',
      '研究什么',
      '为什么值得关注'
    ]);

    return raw
      .split(/\r?\n+/)
      .map(line => cleanMarkupText(line))
      .filter(Boolean)
      .map(line => {
        const match = line.match(/^(.+?)[？?]?\s*[：:]\s*(.+)$/);
        if (!match) return null;
        const label = match[1].trim();
        const text = match[2].trim();
        if (!allowedLabels.has(label) || !text) return null;
        return { label, text };
      })
      .filter(Boolean);
  };

  const createSummary = (paper) => {
    const rawSummary = String(paper.summaryZh || '').trim();
    if (!rawSummary) return null;

    const wrap = document.createElement('div');
    wrap.className = 'radar-summary';

    const label = document.createElement('div');
    label.className = 'radar-summary__label';

    const labelText = document.createElement('span');
    labelText.textContent = 'AI 中文导读';
    label.appendChild(labelText);

    if (paper.summarySource === 'title-only') {
      const caveat = document.createElement('span');
      caveat.className = 'radar-summary__caveat';
      caveat.textContent = '基于标题';
      caveat.title = '未获取到可靠英文摘要，因此该导读仅根据论文标题概括研究主题。';
      label.appendChild(caveat);
    }

    wrap.appendChild(label);

    const points = parseGuidePoints(rawSummary);
    if (points.length >= 2) {
      points.forEach(point => {
        const row = document.createElement('p');
        row.className = 'radar-summary__text';
        row.lang = 'zh-CN';

        const pointLabel = document.createElement('strong');
        pointLabel.textContent = `${point.label}：`;
        row.append(pointLabel, document.createTextNode(point.text));
        wrap.appendChild(row);
      });
    } else {
      const summary = document.createElement('p');
      summary.className = 'radar-summary__text';
      summary.lang = 'zh-CN';
      summary.textContent = cleanMarkupText(rawSummary);
      wrap.appendChild(summary);
    }

    return wrap;
  };

  const createPaperItem = (paper) => {
    const item = document.createElement('a');
    item.className = 'radar-item';
    item.href = paper.link;
    item.target = '_blank';
    item.rel = 'noopener noreferrer';

    const titleRow = document.createElement('div');
    titleRow.className = 'radar-title-row';

    const title = document.createElement('h3');
    title.className = 'radar-title';
    title.textContent = cleanMarkupText(paper.title) || 'Untitled paper';

    const tags = document.createElement('div');
    tags.className = 'radar-tags';
    (paper.matchedKeywords || []).forEach(keyword => tags.appendChild(createTag(keyword)));

    titleRow.append(title, tags);

    const authors = document.createElement('p');
    authors.className = 'radar-authors';
    authors.textContent = cleanMarkupText(paper.authors) || 'Authors not listed';

    const journal = document.createElement('p');
    journal.className = 'radar-journal';
    journal.textContent = cleanMarkupText(paper.journal) || 'Publication venue not listed';

    item.append(titleRow, authors, journal);
    const summary = createSummary(paper);
    if (summary) item.appendChild(summary);
    return item;
  };

  const renderPapers = () => {
    list.replaceChildren();
    const allPapers = Array.isArray(payload?.papers) ? payload.papers : [];
    const visiblePapers = activeKeyword === 'All'
      ? allPapers
      : allPapers.filter(paper => (paper.matchedKeywords || []).includes(activeKeyword));
    const guideCount = visiblePapers.filter(paper => cleanMarkupText(paper.summaryZh)).length;

    status.textContent = `${visiblePapers.length} verified paper${visiblePapers.length === 1 ? '' : 's'} · ${guideCount} Chinese guide${guideCount === 1 ? '' : 's'} · ${formatUpdatedAt(payload?.generatedAt)}`;

    const byDate = new Map();
    visiblePapers.forEach(paper => {
      if (!paper.publicationDate) return;
      if (!byDate.has(paper.publicationDate)) byDate.set(paper.publicationDate, []);
      byDate.get(paper.publicationDate).push(paper);
    });

    const history = payload?.crawlHistory || {};
    const dates = dateRange();

    if (!dates.length) {
      const empty = document.createElement('div');
      empty.className = 'radar-empty';
      empty.textContent = 'Paper Radar is awaiting its first exact-date crawl.';
      list.appendChild(empty);
      return;
    }

    dates.forEach(dateValue => {
      const day = document.createElement('section');
      day.className = 'radar-day';

      const header = document.createElement('div');
      header.className = 'radar-day__header';

      const dateTitle = document.createElement('h3');
      dateTitle.className = 'radar-day__date';
      dateTitle.textContent = formatDateOnly(dateValue);

      const papers = byDate.get(dateValue) || [];
      const count = document.createElement('span');
      count.className = 'radar-day__count';
      count.textContent = `${papers.length} paper${papers.length === 1 ? '' : 's'}`;

      header.append(dateTitle, count);
      day.appendChild(header);

      if (papers.length) {
        papers
          .sort((a, b) => cleanMarkupText(a.title).localeCompare(cleanMarkupText(b.title)))
          .forEach(paper => day.appendChild(createPaperItem(paper)));
      } else {
        const empty = document.createElement('div');
        empty.className = 'radar-day__empty';
        empty.textContent = history?.[dateValue]?.status === 'success' ? '无' : '未爬取';
        day.appendChild(empty);
      }

      list.appendChild(day);
    });
  };

  fetch(`assets/data/paper-radar.json?v=${Date.now()}`, { cache: 'no-store' })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      payload = data;
      renderFilters();
      renderPapers();
    })
    .catch(error => {
      console.error('Paper Radar data load failed:', error);
      status.textContent = 'Data temporarily unavailable';
      const empty = document.createElement('div');
      empty.className = 'radar-empty';
      empty.textContent = 'Paper Radar data could not be loaded. Please try again later.';
      list.replaceChildren(empty);
    });
});
