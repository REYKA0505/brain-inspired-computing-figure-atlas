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
  const imagePath = figure => `${data.image_prefix ?? ''}${figure.image}`;
  const workKey = figure => (figure.doi || figure.paper).toLowerCase();
  const pageSize = 24;
  const dialog = byId('detail');
  const resultsTitle = byId('results-title');
  const search = byId('search');
  const type = byId('type');
  const journal = byId('journal');
  const sort = byId('sort');
  const reset = byId('reset');
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
    byId('detail-image').src = imagePath(figure);
    byId('detail-image').alt = figure.figure_title;
    byId('detail-preview').href = imagePath(figure);
    byId('detail-title').textContent = figure.figure_title;
    byId('detail-paper').textContent = figure.paper;
    const source = [figure.journal, figure.version].filter(Boolean).join(' ');
    byId('detail-citation').textContent = [figure.author, source, figure.year, figure.doi && `DOI ${figure.doi}`]
      .filter(Boolean).join(' · ');
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
    setDetailLink('license-evidence', figure.license_evidence);
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

  function makeCard(figure, index) {
    const card = cardTemplate.cloneNode(true);
    const preview = card.querySelector('.preview');
    preview.setAttribute('aria-label', `查看 ${figure.label}：${figure.figure_title}`);
    preview.addEventListener('click', () => showFigure(index));
    preview.querySelector('img').src = imagePath(figure);
    card.querySelector('.card-topic').textContent = figure.category;
    card.querySelector('.card-label').textContent = figure.label;
    const title = card.querySelector('.card-title');
    title.textContent = figure.figure_title;
    title.title = figure.figure_title;
    const paper = card.querySelector('.card-paper');
    paper.textContent = figure.paper;
    paper.title = figure.paper;
    const source = card.querySelector('.card-journal');
    source.textContent = [figure.journal, figure.year, figure.local_only && '本地'].filter(Boolean).join(' · ');
    source.title = source.textContent;
    const link = card.querySelector('.card-source');
    link.href = figure.paper_url;
    link.setAttribute('aria-label', `查看论文：${figure.paper}`);
    return card;
  }

  function renderPage() {
    const offset = (page - 1) * pageSize;
    const cards = results.slice(offset, offset + pageSize).map((figure, index) => makeCard(figure, offset + index));
    byId('grid').replaceChildren(...cards);
    const pageCount = Math.ceil(results.length / pageSize);
    byId('pager').hidden = pageCount < 2;
    byId('page-count').textContent = `${page} / ${pageCount}`;
    previousPage.disabled = page === 1;
    nextPage.disabled = page >= pageCount;
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
  applyFilters();
})();
