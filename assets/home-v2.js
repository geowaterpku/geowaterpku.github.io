(() => {
  const nav = document.querySelector('.primary-nav');
  const reveals = document.querySelectorAll('.reveal-on-scroll');
  const stories = document.querySelectorAll('.home-v2-story');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const methodsTitle = document.querySelector('#how-we-work-title');
  if (methodsTitle) {
    methodsTitle.textContent = 'We are developing a “big data hydrology” program at PKU.';
    const methodsSummary = methodsTitle.nextElementSibling;
    if (methodsSummary) {
      methodsSummary.textContent = 'Our spatially explicit, river-centric approach brings together four complementary methodological pillars to observe, represent, model, and parameterize heterogeneous river systems.';
    }
  }

  const methodsFigure = document.querySelector('.home-methods__media');
  const methodsImage = methodsFigure?.querySelector('img');
  if (methodsImage) {
    methodsImage.src = 'assets/home/how-we-work-framework.svg?v=4';
    methodsImage.alt = 'Four methodological pillars—Earth observation, geospatial information, process-based and data-driven modeling, and spatially informed parameterization—supporting the Big Data Hydrology program at Peking University';
  }
  const methodsCaption = methodsFigure?.querySelector('figcaption');
  if (methodsCaption) methodsCaption.textContent = 'Four methodological pillars of our Big Data Hydrology program at PKU';

  const newsSection = document.querySelector('.home-v2-news');
  const newsList = newsSection?.querySelector('.home-v2-news-list');
  if (newsList) {
    newsList.querySelectorAll('article').forEach((item, index) => {
      if (index < 2) item.classList.add('home-v2-news-hiring');
    });
  }

  const newsHeading = newsSection?.querySelector('.home-v2-heading');
  if (newsHeading && !newsSection.querySelector('.home-v2-news-update-note')) {
    const updateNote = document.createElement('p');
    updateNote.className = 'home-v2-news-update-note';
    updateNote.textContent = 'News from January 2025 to the present is currently being updated.';
    newsHeading.insertAdjacentElement('afterend', updateNote);
  }

  if (!document.getElementById('home-news-refinement-style')) {
    const newsStyle = document.createElement('style');
    newsStyle.id = 'home-news-refinement-style';
    newsStyle.textContent = `
      .lab-home-v2 .home-v2-news-list article.home-v2-news-hiring{
        margin:0;
        padding-left:18px;
        padding-right:18px;
        background:rgba(91,153,176,.09);
        box-shadow:inset 3px 0 rgba(77,139,164,.28);
      }
      .lab-home-v2 .home-v2-news-update-note{
        max-width:760px;
        margin:-24px 0 24px;
        color:#7d9099;
        font-size:.78rem;
        font-weight:450;
        line-height:1.5;
        letter-spacing:.01em;
      }
      @media(max-width:680px){
        .lab-home-v2 .home-v2-news-list article.home-v2-news-hiring{padding-left:12px;padding-right:12px}
        .lab-home-v2 .home-v2-news-update-note{margin:-16px 0 20px;font-size:.75rem}
      }
    `;
    document.head.appendChild(newsStyle);
  }

  document.querySelector('.home-methods__enabling')?.remove();

  const updateNav = () => nav?.classList.toggle('is-scrolled', window.scrollY > 20);
  updateNav();
  window.addEventListener('scroll', updateNav, { passive: true });

  if (reduceMotion || !('IntersectionObserver' in window)) {
    reveals.forEach((item) => item.classList.add('is-visible'));
    return;
  }

  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.14, rootMargin: '0px 0px -7% 0px' });

  const storyObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => entry.target.classList.toggle('is-active', entry.isIntersecting));
  }, { threshold: 0.28 });

  reveals.forEach((item) => revealObserver.observe(item));
  stories.forEach((story) => storyObserver.observe(story));
})();