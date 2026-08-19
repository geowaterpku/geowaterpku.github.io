(() => {
  const nav = document.querySelector('.primary-nav');
  const reveals = document.querySelectorAll('.reveal-on-scroll');
  const stories = document.querySelectorAll('.home-v2-story');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const questionsTitle = document.querySelector('#questions-title');
  if (questionsTitle) questionsTitle.textContent = 'Three questions guide our science.';

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
