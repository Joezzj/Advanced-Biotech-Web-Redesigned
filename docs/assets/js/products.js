(function () {
  'use strict';

  const searchInput = document.querySelector('#product-search');

  if (!searchInput) {
    return;
  }

  const productCards = Array.from(document.querySelectorAll('[data-product]'));
  const filterButtons = Array.from(document.querySelectorAll('[data-filter]'));
  const clearButton = document.querySelector('#clear-search');
  const resetButton = document.querySelector('#reset-filters');
  const resultCount = document.querySelector('#result-count');
  const emptyState = document.querySelector('#empty-state');

  let selectedCategory = 'all';

  const productText = new Map();
  productCards.forEach(function (card) {
    productText.set(card, card.textContent.toLocaleLowerCase());
  });

  document.querySelectorAll('[data-enhanced]').forEach(function (element) {
    element.hidden = false;
  });

  function filterProducts(updateUrl) {
    const searchText = searchInput.value.trim().toLocaleLowerCase();
    const keywords = searchText.split(/\s+/).filter(Boolean);
    let matchingProducts = 0;

    productCards.forEach(function (card) {
      const matchesCategory = selectedCategory === 'all'
        || card.dataset.category === selectedCategory;
      const matchesSearch = keywords.every(function (keyword) {
        return productText.get(card).includes(keyword);
      });

      card.hidden = !(matchesCategory && matchesSearch);

      if (!card.hidden) {
        matchingProducts += 1;
      }
    });

    filterButtons.forEach(function (button) {
      const isSelected = button.dataset.filter === selectedCategory;
      button.setAttribute('aria-pressed', String(isSelected));
    });

    const allLabel = matchingProducts === productCards.length ? 'all ' : '';
    const productLabel = matchingProducts === 1 ? 'product' : 'products';
    resultCount.textContent = `Showing ${allLabel}${matchingProducts} ${productLabel}`;
    emptyState.hidden = matchingProducts > 0;
    clearButton.hidden = searchInput.value.length === 0;

    if (updateUrl) {
      saveFiltersToUrl();
    }
  }

  function saveFiltersToUrl() {
    // Local HTML files still work; history changes are only used on a server.
    if (location.protocol === 'file:') {
      return;
    }

    const url = new URL(location.href);
    const searchText = searchInput.value.trim();

    if (selectedCategory === 'all') {
      url.searchParams.delete('category');
    } else {
      url.searchParams.set('category', selectedCategory);
    }

    if (searchText) {
      url.searchParams.set('q', searchText);
    } else {
      url.searchParams.delete('q');
    }

    const linkedProduct = productCards.find(function (card) {
      return card.id === url.hash.slice(1);
    });

    if (linkedProduct && linkedProduct.hidden) {
      url.hash = '';
    }

    history.replaceState(null, '', url);
  }

  function showLinkedProduct() {
    const productId = location.hash.slice(1);
    const card = productCards.find(function (product) {
      return product.id === productId;
    });

    if (!card) {
      return;
    }

    if (card.hidden) {
      selectedCategory = 'all';
      searchInput.value = '';
      filterProducts(true);
    }

    card.scrollIntoView({ block: 'start', behavior: 'instant' });
  }

  function restoreFilters() {
    const parameters = new URLSearchParams(location.search);
    const category = parameters.get('category');
    const categoryExists = filterButtons.some(function (button) {
      return button.dataset.filter === category;
    });

    selectedCategory = categoryExists ? category : 'all';
    searchInput.value = parameters.get('q') || '';
    filterProducts(false);
    showLinkedProduct();
  }

  filterButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectedCategory = button.dataset.filter;
      filterProducts(true);
    });
  });

  searchInput.addEventListener('input', function () {
    filterProducts(true);
  });

  clearButton.addEventListener('click', function () {
    searchInput.value = '';
    filterProducts(true);
    searchInput.focus();
  });

  resetButton.addEventListener('click', function () {
    selectedCategory = 'all';
    searchInput.value = '';
    filterProducts(true);
    searchInput.focus();
  });

  window.addEventListener('popstate', restoreFilters);
  window.addEventListener('hashchange', showLinkedProduct);
  restoreFilters();
})();
