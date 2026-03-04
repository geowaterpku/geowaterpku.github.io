document.addEventListener('DOMContentLoaded', () => {
  const currentPage = document.body.dataset.page;
  if (!currentPage) return;

  document.querySelectorAll('.nav-links a[data-page]').forEach(link => {
    const isActive = link.dataset.page === currentPage;
    link.classList.toggle('active', isActive);
    if (isActive) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
});
