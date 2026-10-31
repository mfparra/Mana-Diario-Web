/* Popover das referências bíblicas (AGENTS.md §7, DESIGN.md §6).
 * Hover/foco: abre após ~150 ms. Toque: o 1º toque abre, o 2º navega. Esc fecha. */
(() => {
  'use strict';
  const ATRASO_MS = 150;
  const MAX_VERSICULOS = 6;
  const cache = new Map();
  const semHover = window.matchMedia('(hover: none)');
  let pop = null, aberto = null, timerAbrir = 0, timerFechar = 0;

  function criarPopover() {
    pop = document.createElement('div');
    pop.id = 'ref-popover';
    pop.className = 'ref-popover';
    pop.setAttribute('role', 'tooltip');
    pop.hidden = true;
    pop.addEventListener('mouseenter', () => clearTimeout(timerFechar));
    pop.addEventListener('mouseleave', agendarFechar);
    document.body.appendChild(pop);
  }

  async function buscar(ref) {
    if (!cache.has(ref)) {
      cache.set(ref, fetch('/api/passagem?ref=' + encodeURIComponent(ref))
        .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .catch((e) => { cache.delete(ref); throw e; }));
    }
    return cache.get(ref);
  }

  function el(tag, classe, texto) {
    const e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto !== undefined) e.textContent = texto;
    return e;
  }

  function montar(dados, link) {
    pop.replaceChildren();
    pop.appendChild(el('p', 'pop-ref', dados.referencia));
    const corpo = el('p', 'pop-texto');
    dados.versiculos.slice(0, MAX_VERSICULOS).forEach((v, i) => {
      if (i) corpo.append(' ');
      corpo.appendChild(el('sup', '', v.numero));
      corpo.append(v.texto);
    });
    if (dados.versiculos.length > MAX_VERSICULOS) {
      corpo.append(' ');
      corpo.appendChild(el('span', 'pop-mais', '… continuar lendo'));
    }
    pop.appendChild(corpo);
    const rodape = el('div', 'pop-rodape');
    const abrir = el('a', '', 'Abrir na Bíblia →');
    abrir.href = dados.url;
    rodape.appendChild(abrir);
    rodape.appendChild(el('span', 'pop-edicao', dados.edicao));
    const fechar = el('button', 'pop-fechar', 'Fechar');
    fechar.type = 'button';
    fechar.addEventListener('click', fecharAgora);
    rodape.appendChild(fechar);
    pop.appendChild(rodape);
  }

  function posicionar(link) {
    if (window.matchMedia('(max-width: 899px)').matches) { pop.style.top = ''; return; }
    const r = link.getBoundingClientRect();
    const largura = pop.offsetWidth, altura = pop.offsetHeight;
    const x = Math.max(8, Math.min(r.left, window.innerWidth - largura - 8));
    const abaixo = window.innerHeight - r.bottom > altura + 16 || r.top < altura + 16;
    pop.classList.toggle('acima', !abaixo);
    pop.style.left = x + window.scrollX + 'px';
    pop.style.top = (abaixo ? r.bottom + 10 : r.top - altura - 10) + window.scrollY + 'px';
    pop.style.setProperty('--seta-x', Math.max(12, Math.min(r.left - x + 12, largura - 24)) + 'px');
  }

  async function abrir(link) {
    clearTimeout(timerFechar);
    if (aberto === link && !pop.hidden) return;
    if (!pop) criarPopover();
    aberto = link;
    try {
      const dados = await buscar(link.dataset.ref);
      if (aberto !== link) return; // o usuário já foi para outro link
      montar(dados, link);
    } catch (e) {
      return; // referência sem passagem: o link continua funcionando normalmente
    }
    pop.hidden = false;
    link.setAttribute('aria-describedby', pop.id);
    posicionar(link);
  }

  function fecharAgora() {
    clearTimeout(timerAbrir);
    clearTimeout(timerFechar);
    if (aberto) aberto.removeAttribute('aria-describedby');
    if (pop) pop.hidden = true;
    aberto = null;
  }

  function agendarFechar() {
    clearTimeout(timerAbrir);
    clearTimeout(timerFechar);
    timerFechar = setTimeout(fecharAgora, 200);
  }

  function agendarAbrir(link) {
    clearTimeout(timerAbrir);
    timerAbrir = setTimeout(() => abrir(link), ATRASO_MS);
  }

  const alvo = (e) => (e.target instanceof Element ? e.target.closest('a.ref[data-ref]') : null);

  document.addEventListener('mouseover', (e) => { const l = alvo(e); if (l && !semHover.matches) agendarAbrir(l); });
  document.addEventListener('mouseout', (e) => { if (alvo(e) && !semHover.matches) agendarFechar(); });
  document.addEventListener('focusin', (e) => { const l = alvo(e); if (l) agendarAbrir(l); });
  document.addEventListener('focusout', (e) => { if (alvo(e)) agendarFechar(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') fecharAgora(); });
  window.addEventListener('scroll', () => { if (aberto && !pop.hidden) posicionar(aberto); }, { passive: true });
  window.addEventListener('resize', () => { if (aberto && !pop.hidden) posicionar(aberto); });

  document.addEventListener('click', (e) => {
    const l = alvo(e);
    if (l && semHover.matches) {
      if (aberto === l && pop && !pop.hidden) return; // 2º toque: segue o link
      e.preventDefault();
      abrir(l);
    } else if (pop && !pop.hidden && !pop.contains(e.target)) {
      fecharAgora();
    }
  });
})();
