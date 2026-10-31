/* Seletor de livro/capítulo: ajusta a lista de capítulos ao livro escolhido e navega. */
(() => {
  const form = document.getElementById('ir-para');
  if (!form) return;
  const livro = form.elements.livro, cap = form.elements.cap;
  function montarCapitulos(n, atual) {
    cap.replaceChildren(...Array.from({ length: n }, (_, i) => {
      const o = new Option(String(i + 1), String(i + 1));
      o.selected = i + 1 === atual;
      return o;
    }));
  }
  livro.addEventListener('change', () => {
    montarCapitulos(Number(livro.selectedOptions[0].dataset.capitulos), 1);
    form.requestSubmit();
  });
  cap.addEventListener('change', () => form.requestSubmit());
})();
