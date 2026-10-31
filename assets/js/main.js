(() => {
  const root = document.documentElement;
  const journey = document.querySelector('.journey');
  const steps = Array.from(document.querySelectorAll('.journey-steps li'));
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const size = window.matchMedia('(min-width: 901px) and (min-height: 700px)');
  const sticky = document.querySelector('.journey-sticky');
  const isStatic = new URLSearchParams(location.search).has('static');
  let queued = false;
  function enabled() { return size.matches && !motion.matches && !(navigator.connection && navigator.connection.saveData) && !isStatic; }
  function update() {
    queued = false;
    let active = enabled();
    root.classList.toggle('enhanced', active);
    if (active && sticky && sticky.getBoundingClientRect().height > window.innerHeight + 1) {
      active = false;
      root.classList.remove('enhanced');
    }
    if (!active || !journey) return;
    const rect = journey.getBoundingClientRect();
    const distance = Math.max(1, journey.offsetHeight - window.innerHeight);
    const progress = Math.max(0, Math.min(1, -rect.top / distance));
    journey.style.setProperty('--progress', progress.toFixed(4));
    const current = Math.min(steps.length - 1, Math.floor(progress * steps.length));
    steps.forEach((step, index) => step.classList.toggle('active', index === current));
  }
  function schedule() { if (!queued) { queued = true; requestAnimationFrame(update); } }
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  if (motion.addEventListener) motion.addEventListener('change', schedule);
  if (size.addEventListener) size.addEventListener('change', schedule);
  if (navigator.connection && navigator.connection.addEventListener) navigator.connection.addEventListener('change', schedule);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule);
  update();
})();
