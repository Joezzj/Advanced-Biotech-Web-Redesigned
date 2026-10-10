(function () {
  'use strict';

  document.documentElement.classList.add('js-enabled');

  updateCopyright();
  setupNavigation();

  function updateCopyright() {
    const year = new Date().getFullYear();
    const yearLabels = document.querySelectorAll('[data-year]');

    yearLabels.forEach(function (label) {
      label.textContent = year;
    });
  }

  function setupNavigation() {
    const menuButton = document.querySelector('.menu-toggle');
    const navigation = document.querySelector('#main-nav');
    const mobileScreen = window.matchMedia('(max-width: 700px)');

    if (!menuButton || !navigation) {
      return;
    }

    function setMenuOpen(isOpen) {
      navigation.classList.toggle('is-open', isOpen);
      document.body.classList.toggle('menu-open', isOpen);
      menuButton.setAttribute('aria-expanded', String(isOpen));
      menuButton.setAttribute('aria-label', isOpen ? 'Close menu' : 'Open menu');
    }

    function closeMenu(restoreFocus) {
      setMenuOpen(false);

      if (restoreFocus) {
        menuButton.focus();
      }
    }

    function handleMenuKeys(event) {
      if (menuButton.getAttribute('aria-expanded') !== 'true') {
        return;
      }

      if (event.key === 'Escape') {
        closeMenu(true);
        return;
      }

      if (event.key !== 'Tab' || !mobileScreen.matches) {
        return;
      }

      const links = Array.from(navigation.querySelectorAll('a'));
      const firstItem = menuButton;
      const lastItem = links[links.length - 1];

      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    }

    menuButton.addEventListener('click', function () {
      const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
      setMenuOpen(!isOpen);
    });

    navigation.addEventListener('click', function (event) {
      if (event.target.closest('a')) {
        closeMenu(false);
      }
    });

    document.addEventListener('click', function (event) {
      if (!event.target.closest('.site-header')) {
        closeMenu(false);
      }
    });

    document.addEventListener('keydown', handleMenuKeys);

    mobileScreen.addEventListener('change', function () {
      closeMenu(false);
    });

    window.addEventListener('pageshow', function () {
      closeMenu(false);
    });
  }
})();
