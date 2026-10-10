(function () {
  'use strict';

  const form = document.querySelector('#contact-form');

  if (!form) {
    return;
  }

  const settings = window.AB_CONFIG || {};
  const endpoint = typeof settings.contactEndpoint === 'string'
    ? settings.contactEndpoint.trim()
    : '';
  const submitButton = document.querySelector('#submit-enquiry');
  const submitLabel = submitButton.querySelector('span');
  const statusMessage = document.querySelector('#form-status');
  const emailFallback = document.querySelector('#email-fallback');
  const draftLink = document.querySelector('#email-draft-link');
  const copyButton = document.querySelector('#copy-enquiry');
  const copyArea = document.querySelector('#enquiry-copy');
  const fieldNames = ['name', 'email', 'company', 'interest', 'product', 'message', 'website'];
  const contactEmail = 'info@advancedbiotech.co.nz';

  fillRequestedProduct();

  if (endpoint) {
    submitLabel.textContent = 'Send enquiry';
    document.querySelector('#delivery-note').textContent =
      'Send your enquiry directly to our team. You’ll see a confirmation here '
      + 'when our mail service accepts it.';
  }

  function fillRequestedProduct() {
    const parameters = new URLSearchParams(location.search);

    ['product', 'interest'].forEach(function (fieldName) {
      const requestedValue = parameters.get(fieldName);
      const field = form.elements[fieldName];
      const allowedValue = Array.from(field.options).some(function (option) {
        return option.value === requestedValue;
      });

      if (requestedValue && allowedValue) {
        field.value = requestedValue;
      }
    });
  }

  function readEnquiry() {
    const enquiry = {};

    fieldNames.forEach(function (fieldName) {
      enquiry[fieldName] = form.elements[fieldName].value.trim();
    });

    return enquiry;
  }

  function showMessage(message, state) {
    statusMessage.textContent = message;
    statusMessage.dataset.state = state || 'info';
    statusMessage.hidden = false;
  }

  function prepareEmailDraft(enquiry) {
    const subject = 'Website enquiry: '
      + (enquiry.product || enquiry.interest || 'General enquiry');
    const body = [
      'Hello Advanced Biotech team,',
      '',
      enquiry.message,
      '',
      `Name: ${enquiry.name}`,
      `Email: ${enquiry.email}`,
      `Company: ${enquiry.company || 'Not specified'}`,
      `Interest: ${enquiry.interest}`,
      `Product / application: ${enquiry.product || 'Not specified'}`,
      '',
      'Kind regards,',
      enquiry.name
    ].join('\n');

    draftLink.href = `mailto:${contactEmail}?subject=${encodeURIComponent(subject)}`
      + `&body=${encodeURIComponent(body)}`;
    copyArea.value = `To: ${contactEmail}\nSubject: ${subject}\n\n${body}`;
    emailFallback.hidden = false;
  }

  function validateEnquiry() {
    ['name', 'email', 'company', 'message'].forEach(function (fieldName) {
      const field = form.elements[fieldName];
      field.value = field.value.trim();
    });

    const message = form.elements.message;
    const name = form.elements.name;

    message.setCustomValidity(message.value.length < 10
      ? 'Please enter at least 10 characters about your enquiry.'
      : '');
    name.setCustomValidity(name.value ? '' : 'Please enter your name.');

    return form.reportValidity();
  }

  function setSending(isSending) {
    submitButton.disabled = isSending;
    submitLabel.textContent = isSending ? 'Sending…' : 'Send enquiry';

    if (isSending) {
      form.setAttribute('aria-busy', 'true');
    } else {
      form.removeAttribute('aria-busy');
    }
  }

  async function sendEnquiry(enquiry) {
    const controller = new AbortController();
    const timeoutMs = Number(settings.requestTimeoutMs) || 20000;
    const timeout = setTimeout(function () {
      controller.abort();
    }, timeoutMs);

    setSending(true);
    statusMessage.hidden = true;
    emailFallback.hidden = true;

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(enquiry),
        signal: controller.signal,
        credentials: 'omit'
      });
      const result = await response.json().catch(function () {
        return {};
      });

      if (!response.ok || result.success !== true) {
        const message = response.status === 429
          ? 'Too many enquiries in a short time. Please try later or email us directly.'
          : 'We couldn’t send your enquiry. Your message is still here; '
            + 'please try again or use the email draft below.';
        throw new Error(message);
      }

      showMessage(
        'Thank you. Our mail service has accepted your enquiry. '
          + 'We look forward to learning more about your project.',
        'success'
      );
      form.reset();
      copyArea.value = '';
      copyArea.hidden = true;
    } catch (error) {
      prepareEmailDraft(enquiry);

      const message = error.name === 'AbortError'
        ? 'We couldn’t confirm delivery before the connection timed out. '
          + 'Your message is preserved. Please check before sending again, '
          + 'or contact us by email.'
        : error.message || 'Unable to send. Please use the email draft below.';
      showMessage(message, 'error');
    } finally {
      clearTimeout(timeout);
      setSending(false);
      statusMessage.focus();
    }
  }

  async function copyEnquiry() {
    prepareEmailDraft(readEnquiry());

    try {
      if (!navigator.clipboard || !window.isSecureContext) {
        throw new Error('Clipboard unavailable');
      }

      await navigator.clipboard.writeText(copyArea.value);
      copyButton.textContent = 'Copied';
      showMessage('Enquiry copied. Paste it into an email to ' + contactEmail + '.');
    } catch (error) {
      copyArea.hidden = false;
      copyArea.focus();
      copyArea.select();
      showMessage('Select and copy the enquiry below, then paste it into your email app.');
    }
  }

  async function submitEnquiry(event) {
    event.preventDefault();

    if (submitButton.disabled || !validateEnquiry()) {
      return;
    }

    const enquiry = readEnquiry();

    if (enquiry.website) {
      showMessage('Please leave the extra field empty and try again.', 'error');
      return;
    }

    if (endpoint) {
      await sendEnquiry(enquiry);
    } else {
      prepareEmailDraft(enquiry);
      showMessage(
        'Your enquiry is ready. Choose “Open email draft” below, '
          + 'then send it from your email app. Nothing has been sent yet.'
      );
      statusMessage.focus();
    }
  }

  form.addEventListener('submit', submitEnquiry);
  copyButton.addEventListener('click', copyEnquiry);

  form.addEventListener('input', function () {
    if (!emailFallback.hidden) {
      prepareEmailDraft(readEnquiry());
    }

    copyButton.textContent = 'Copy enquiry text';

    if (statusMessage.dataset.state === 'success') {
      statusMessage.hidden = true;
    }
  });

  form.addEventListener('change', function () {
    if (!emailFallback.hidden) {
      prepareEmailDraft(readEnquiry());
    }
  });

  ['name', 'message'].forEach(function (fieldName) {
    form.elements[fieldName].addEventListener('input', function () {
      form.elements[fieldName].setCustomValidity('');
    });
  });
})();
