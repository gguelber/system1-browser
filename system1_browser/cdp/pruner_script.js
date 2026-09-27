/**
 * system1-browser DOM Pruner v2 (Deep Shadow DOM & iFrame Support)
 * Extracts actionable, visible interactive elements into a compact JSON array (~300 tokens).
 * Recursively traverses Shadow Roots and same-origin iFrames.
 * Detects busy spinners and page loading states to prevent premature actions.
 */
(() => {
  const isVisible = (elem) => {
    if (!elem) return false;
    const style = window.getComputedStyle(elem);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
    const rect = elem.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return false;
    // Must be at least partially visible or near the viewport
    const windowHeight = window.innerHeight || document.documentElement.clientHeight;
    const windowWidth = window.innerWidth || document.documentElement.clientWidth;
    const vertInView = rect.top <= windowHeight + 200 && rect.bottom >= -200;
    const horInView = rect.left <= windowWidth + 200 && rect.right >= -200;
    return vertInView && horInView;
  };

  const getCleanText = (elem) => {
    // 1. Value or Placeholder
    if (elem.value && typeof elem.value === 'string' && elem.value.trim().length > 0) {
      return elem.value.trim();
    }
    if (elem.placeholder && elem.placeholder.trim().length > 0) {
      return elem.placeholder.trim();
    }
    // 2. Aria-label / title
    const aria = elem.getAttribute('aria-label') || elem.getAttribute('title') || '';
    if (aria.trim().length > 0) return aria.trim();

    // 3. Inner text (first direct text child or trimmed text)
    let text = elem.innerText || elem.textContent || '';
    text = text.replace(/\s+/g, ' ').trim();
    return text.substring(0, 60);
  };

  const getElementPath = (el) => {
    if (el.id) return `#${el.id}`;
    let path = el.tagName.toLowerCase();
    if (el.name) return `${path}[name="${el.name}"]`;
    if (el.className && typeof el.className === 'string') {
      const classes = el.className.split(' ').filter(c => c.trim().length > 0 && !c.includes(':')).slice(0, 2);
      if (classes.length > 0) path += '.' + classes.join('.');
    }
    return path;
  };

  // Check for active page loading or busy spinners
  const checkLoading = () => {
    if (document.readyState === 'loading') {
      return { isLoading: true, reason: 'Documento ainda carregando (readyState=loading)' };
    }
    const busyEl = document.querySelector('[aria-busy="true"], .spinner, .loading-spinner, .loading-overlay, .carregando, .mat-progress-spinner, .v-progress-circular, .ant-spin-spinning');
    if (busyEl && isVisible(busyEl)) {
      return { isLoading: true, reason: 'Spinner de carregamento ativo detectado na tela' };
    }
    return { isLoading: false, reason: '' };
  };

  const selectorQuery = 'button, input, select, textarea, a[href], [role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="tab"], [onclick], [tabindex="0"]';
  
  const actionable = [];
  const seenRects = new Set();

  const traverseNodes = (root, depth = 0) => {
    if (!root || depth > 4 || actionable.length >= 50) return;

    // 1. Collect actionable candidates at this root level
    try {
      const rawElements = Array.from(root.querySelectorAll(selectorQuery));
      for (let i = 0; i < rawElements.length; i++) {
        const el = rawElements[i];
        if (!isVisible(el)) continue;

        const rect = el.getBoundingClientRect();
        const rectKey = `${Math.round(rect.top)}_${Math.round(rect.left)}_${Math.round(rect.width)}_${Math.round(rect.height)}`;
        if (seenRects.has(rectKey)) continue;
        seenRects.add(rectKey);

        const tag = el.tagName.toLowerCase();
        const type = el.getAttribute('type') || (tag === 'textarea' ? 'textarea' : (tag === 'select' ? 'select' : ''));
        const label = getCleanText(el);
        const name = el.getAttribute('name') || '';
        const id = el.id || '';
        const role = el.getAttribute('role') || '';
        const disabled = el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';

        // Skip totally empty links without identifiers
        if (!label && !name && !id && tag === 'a') continue;

        actionable.push({
          id: actionable.length,
          tag: tag,
          type: type,
          label: label,
          name: name,
          dom_id: id,
          role: role,
          disabled: disabled,
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2),
          selector: getElementPath(el)
        });

        if (actionable.length >= 50) break;
      }
    } catch (e) {
      // Ignore cross-origin security restrictions on querySelector
    }

    // 2. Traverse Shadow DOMs
    try {
      const allElements = Array.from(root.querySelectorAll('*'));
      for (const el of allElements) {
        if (el.shadowRoot) {
          traverseNodes(el.shadowRoot, depth + 1);
        }
      }
    } catch (e) {}

    // 3. Traverse same-origin iFrames
    try {
      const iframes = Array.from(root.querySelectorAll('iframe, frame'));
      for (const iframe of iframes) {
        try {
          const doc = iframe.contentDocument || (iframe.contentWindow && iframe.contentWindow.document);
          if (doc) {
            traverseNodes(doc, depth + 1);
          }
        } catch (crossErr) {
          // Cross-origin iframe, ignore
        }
      }
    } catch (e) {}
  };

  traverseNodes(document);

  // Extract visible alert, toast or notification messages
  const alertNodes = Array.from(document.querySelectorAll('[role="alert"], .alert, .error, .toast, .snackbar, .notification'));
  const alerts = alertNodes
    .filter(isVisible)
    .map(el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().substring(0, 120))
    .filter(t => t.length > 0);

  const loadingStatus = checkLoading();

  return {
    url: window.location.href,
    title: document.title,
    alerts: alerts,
    isLoading: loadingStatus.isLoading,
    loadingReason: loadingStatus.reason,
    elementCount: actionable.length,
    elements: actionable
  };
})();
