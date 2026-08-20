(() => {
  const nav = document.querySelector('.primary-nav');
  const reveals = document.querySelectorAll('.reveal-on-scroll');
  const stories = document.querySelectorAll('.home-v2-story');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const questionsTitle = document.querySelector('#questions-title');
  if (questionsTitle) questionsTitle.textContent = 'Three questions guide our science.';

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