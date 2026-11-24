(() => {
  const byId = id => document.getElementById(id);
  const data = window.GALLERY_DATA;
  const notice = byId('notice');
  if (!Array.isArray(data?.figures)) {
    notice.textContent = '未找到本地图例数据。';
    notice.hidden = false;
    return;
  }

  const figures = [...(data.local_figures ?? []), ...data.figures];
  const imageSizes = { ...data.image_sizes, ...data.local_image_sizes };
  const imagePath = figure => `${data.image_prefix ?? ''}${figure.image}`;
  const workKey = figure => (figure.doi || figure.paper).toLowerCase();
  const pageSize = 24;
  const dialog = byId('detail');
  const resultsTitle = byId('results-title');
  const search = byId('search');
  const type = byId('type');
  const journal = byId('journal');
  const filterPanel = byId('figure-filters');
  const filterSummary = filterPanel.querySelector('summary');
  const activeFilters = byId('active-filters');
  const chipTemplate = byId('filter-chip').content.firstElementChild;
  const sort = byId('sort');
  const reset = byId('reset');
  const grid = byId('grid');
  const layoutButtons = document.querySelectorAll('.layout-switch button');
  const layoutPreference = 'neuro-atlas-layout';
  const masonryObserver = new ResizeObserver(packMasonry);
  const previousPage = byId('previous-page');
  const nextPage = byId('next-page');
  const previousFigure = byId('previous-figure');
  const nextFigure = byId('next-figure');
  const closeDetail = byId('close-detail');
  const cardTemplate = byId('figure-card').content.firstElementChild;
  const topicCounts = new Map([['', figures.length]]);
  const topicButtons = new Map();
  let topic = '';
  let results = [];
  let page = 1;
  let detailIndex = 0;

  const searchable = figures.map(figure => ({
    figure,
    text: [
      figure.paper, figure.figure_title, figure.caption, figure.author, figure.journal,
      figure.category, figure.label, figure.id, figure.pmcid, figure.doi, figure.team, figure.version, ...figure.tags,
    ].join(' ').toLocaleLowerCase(),
  }));

  for (const { category } of figures) {
    topicCounts.set(category, (topicCounts.get(category) ?? 0) + 1);
  }
  for (const [name, count] of topicCounts) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'topic-button';
    const label = document.createElement('span');
    label.textContent = name || '全部图例';
    const total = document.createElement('span');
    total.className = 'topic-count';
    total.textContent = count.toLocaleString();
    button.append(label, total);
    button.addEventListener('click', () => {
      topic = name;
      applyFilters();
    });
    topicButtons.set(name, button);
    byId('topic-list').append(button);
  }

  for (const value of new Set(figures.flatMap(figure => figure.tags))) {
    type.add(new Option(value, value));
  }
  for (const value of [...new Set(figures.map(figure => figure.journal))].sort()) {
    journal.add(new Option(value, value));
  }
  byId('figure-count').textContent = figures.length.toLocaleString();
  byId('paper-count').textContent = new Set(figures.map(workKey)).size.toLocaleString();
  byId('snapshot-date').dateTime = data.created;
  byId('snapshot-date').textContent = data.created;

  function showFigure(index) {
    const figure = results[index];
    if (!figure) return;
    detailIndex = index;
    byId('detail-label').textContent = `${figure.category} · ${figure.label}`;
    byId('detail-position').textContent = `${index + 1} / ${results.length}`;
    const preview = byId('detail-preview');
    loadPreview(preview, figure);
    byId('detail-image').alt = figure.figure_title;
    preview.href = imagePath(figure);
    byId('detail-title').textContent = figure.figure_title;
    byId('detail-paper').textContent = figure.paper;
    const source = [figure.journal, figure.version].filter(Boolean).join(' ');
    byId('detail-citation').textContent = [figure.author, source, figure.year]
      .filter(Boolean).join(' · ');
    byId('detail-doi').hidden = !figure.doi;
    byId('detail-doi-link').textContent = figure.doi || '';
    setDetailLink('detail-doi-link', figure.doi && (figure.doi_url || `https://doi.org/${figure.doi}`));
    byId('detail-team').textContent = figure.team || '';
    byId('detail-team').hidden = !figure.team;
    byId('detail-rights').textContent = figure.rights_note || '';
    byId('detail-rights').hidden = !figure.rights_note;
    byId('caption-heading').textContent = figure.caption_label || '原始图注';
    byId('detail-caption').textContent = figure.caption;
    byId('paper-link').href = figure.paper_url;
    setDetailLink('original-link', figure.original);
    byId('original-link-label').textContent = figure.original_label || (figure.pdf_crop ? '原图所在页' : '查看原图');
    setDetailLink('license-link', figure.license);
    byId('license-link').textContent = figure.license === 'https://creativecommons.org/licenses/by/4.0/'
      ? '文章许可 · CC BY 4.0' : '文章许可';
    setDetailLink('license-evidence', figure.license_evidence);
    byId('detail-license').hidden = !figure.license && !figure.license_evidence && !figure.rights_note;
    previousFigure.disabled = index === 0;
    nextFigure.disabled = index === results.length - 1;
    if (!dialog.open) dialog.showModal();
    if (document.activeElement.disabled) closeDetail.focus();
    dialog.scrollTop = 0;
  }

  function setDetailLink(id, url) {
    const link = byId(id);
    link.hidden = !url;
    if (url) link.href = url;
    else link.removeAttribute('href');
  }

  function loadPreview(container, figure) {
    const image = container.querySelector('img');
    const placeholder = container.querySelector('.preview-error');
    image.hidden = false;
    placeholder.hidden = true;
    image.onerror = () => {
      image.hidden = true;
      placeholder.hidden = false;
    };
    image.src = imagePath(figure);
  }

  function setPreviewRatio(card, width, height) {
    const ratio = width / height;
    if (Number.isFinite(ratio) && ratio > 0) {
      card.style.setProperty('--preview-ratio', Math.max(0.82, Math.min(3.2, ratio)));
    }
  }

  function makeCard(figure, index) {
    const card = cardTemplate.cloneNode(true);
    const preview = card.querySelector('.preview');
    const image = preview.querySelector('img');
    const size = imageSizes[figure.image];
    if (size) {
      setPreviewRatio(card, ...size);
    } else {
      image.addEventListener('load', () => setPreviewRatio(card, image.naturalWidth, image.naturalHeight), { once: true });
    }
    preview.setAttribute('aria-label', `查看 ${figure.label}：${figure.figure_title}`);
    preview.addEventListener('click', () => showFigure(index));
    loadPreview(preview, figure);
    card.querySelector('.card-topic').textContent = figure.category;
    card.querySelector('.card-label').textContent = figure.label;
    const title = card.querySelector('.card-title');
    title.textContent = figure.figure_title;
    title.title = figure.figure_title;
    const source = card.querySelector('.card-journal');
    source.textContent = [figure.journal, figure.year, figure.local_only && '本地'].filter(Boolean).join(' · ');
    source.title = source.textContent;
    const link = card.querySelector('.card-source');
    link.href = figure.paper_url;
    link.setAttribute('aria-label', `查看论文：${figure.paper}`);
    return card;
  }

  function packMasonry() {
    if (grid.dataset.layout !== 'masonry') return;
    const style = getComputedStyle(grid);
    const rowHeight = Number.parseFloat(style.gridAutoRows);
    if (!rowHeight) return;
    const gap = Number.parseFloat(style.columnGap);

    // Measure every card before writing spans so grid placement keeps DOM order.
    const spans = Array.from(grid.children, card => Math.ceil((card.getBoundingClientRect().height + gap) / rowHeight));
    spans.forEach((span, index) => grid.children[index].style.setProperty('--masonry-span', span));
  }

  function setLayout(layout) {
    grid.dataset.layout = layout;
    for (const button of layoutButtons) button.setAttribute('aria-pressed', button.dataset.layout === layout);
    packMasonry();
  }

  function renderPage() {
    const offset = (page - 1) * pageSize;
    const cards = results.slice(offset, offset + pageSize).map((figure, index) => makeCard(figure, offset + index));
    masonryObserver.disconnect();
    grid.replaceChildren(...cards);
    packMasonry();
    for (const card of cards) masonryObserver.observe(card);
    const pageCount = Math.ceil(results.length / pageSize);
    byId('pager').hidden = pageCount < 2;
    byId('page-count').textContent = `${page} / ${pageCount}`;
    previousPage.disabled = page === 1;
    nextPage.disabled = page >= pageCount;
  }

  function renderActiveFilters() {
    const chips = [type, journal].filter(control => control.value).map(control => {
      const chip = chipTemplate.cloneNode(true);
      const label = control.selectedOptions[0].textContent;
      chip.querySelector('span').textContent = label;
      chip.setAttribute('aria-label', `清除筛选：${label}`);
      chip.addEventListener('click', () => {
        control.value = '';
        applyFilters();
        (activeFilters.firstElementChild || filterSummary).focus();
      });
      return chip;
    });
    activeFilters.replaceChildren(...chips);
    activeFilters.hidden = chips.length === 0;
  }

  function applyFilters() {
    const query = search.value.trim().toLocaleLowerCase();
    const terms = query ? query.split(/\s+/) : [];
    const selectedType = type.value;
    const selectedJournal = journal.value;
    results = searchable.filter(({ figure, text }) => (
      (!topic || figure.category === topic)
      && (!selectedType || figure.tags.includes(selectedType))
      && (!selectedJournal || figure.journal === selectedJournal)
      && terms.every(term => text.includes(term))
    )).map(({ figure }) => figure);
    if (sort.value !== 'curated') {
      const order = sort.value === 'recent' ? -1 : 1;
      results.sort((a, b) => order * (a.year - b.year));
    }

    for (const [name, button] of topicButtons) button.setAttribute('aria-pressed', name === topic);
    resultsTitle.textContent = topic || '全部图例';
    byId('results-count').textContent = `${results.length.toLocaleString()} 张`;
    reset.disabled = !topic && !query && !selectedType && !selectedJournal && sort.value === 'curated';
    notice.hidden = results.length > 0;
    notice.textContent = '没有符合当前条件的图例。';
    renderActiveFilters();
    page = 1;
    renderPage();
  }

  function changePage(step) {
    page += step;
    renderPage();
    resultsTitle.focus({ preventScroll: true });
    resultsTitle.scrollIntoView({ block: 'start' });
  }

  search.addEventListener('input', applyFilters);
  for (const control of [type, journal, sort]) control.addEventListener('change', applyFilters);
  for (const button of layoutButtons) {
    button.addEventListener('click', () => {
      setLayout(button.dataset.layout);
      try {
        localStorage.setItem(layoutPreference, button.dataset.layout);
      } catch {
        // Storage is optional for offline browsing.
      }
    });
  }
  filterPanel.addEventListener('keydown', event => {
    if (event.key === 'Escape' && filterPanel.open) {
      filterPanel.open = false;
      filterSummary.focus();
    }
  });
  filterPanel.addEventListener('focusout', event => {
    if (event.relatedTarget && !filterPanel.contains(event.relatedTarget)) filterPanel.open = false;
  });
  document.addEventListener('click', event => {
    if (filterPanel.open && !filterPanel.contains(event.target)) filterPanel.open = false;
  });
  reset.addEventListener('click', () => {
    topic = '';
    search.value = type.value = journal.value = '';
    sort.value = 'curated';
    applyFilters();
    search.focus();
  });
  previousPage.addEventListener('click', () => changePage(-1));
  nextPage.addEventListener('click', () => changePage(1));
  previousFigure.addEventListener('click', () => showFigure(detailIndex - 1));
  nextFigure.addEventListener('click', () => showFigure(detailIndex + 1));
  closeDetail.addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      showFigure(detailIndex + (event.key === 'ArrowLeft' ? -1 : 1));
    }
  });

  const params = new URLSearchParams(location.search);
  const requestedTopic = params.get('topic');
  const requestedJournal = params.get('journal');
  if (topicCounts.has(requestedTopic)) topic = requestedTopic;
  if ([...journal.options].some(option => option.value === requestedJournal)) journal.value = requestedJournal;
  try {
    if (localStorage.getItem(layoutPreference) === 'grid') setLayout('grid');
  } catch {
    // Use the default layout when storage is unavailable.
  }
  applyFilters();
})();
