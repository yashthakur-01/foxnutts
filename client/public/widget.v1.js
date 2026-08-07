/**
 * widget.v1.js
 * Production-ready embeddable chatbot loader script.
 * 
 * Usage on customer site:
 * <script 
 *   src="https://your-domain.com/widget.v1.js" 
 *   data-workspace-id="YOUR_WORKSPACE_ID"
 *   data-position="bottom-right"
 *   async
 * ></script>
 */

(function () {
  'use strict';

  // Prevent double initialization
  if (window.__RAG_CHAT_WIDGET_LOADED__) return;
  window.__RAG_CHAT_WIDGET_LOADED__ = true;

  // Detect script tag and extract custom attributes
  const currentScript = 
    document.currentScript || 
    document.querySelector('script[src*="widget.v1.js"]');

  if (!currentScript) {
    console.error('[Widget] Script element not found.');
    return;
  }

  const workspaceId = currentScript.getAttribute('data-workspace-id');
  const position = currentScript.getAttribute('data-position') || 'bottom-right';

  if (!workspaceId) {
    console.error('[Widget] Missing required attribute: data-workspace-id.');
    return;
  }

  // Determine base host domain from script URL
  let baseUrl = '';
  try {
    const scriptUrl = new URL(currentScript.src);
    baseUrl = scriptUrl.origin;
  } catch (e) {
    baseUrl = window.location.origin;
  }

  // Create iframe element
  const iframe = document.createElement('iframe');
  iframe.id = 'rag-widget-iframe';
  iframe.title = 'AI Assistant Chat Widget';
  iframe.src = `${baseUrl}/embed?workspace_id=${encodeURIComponent(workspaceId)}`;

  // Default floating bubble style (Collapsed)
  const isLeft = position.includes('left');
  const isTop = position.includes('top');

  Object.assign(iframe.style, {
    position: 'fixed',
    bottom: isTop ? 'auto' : '20px',
    top: isTop ? '20px' : 'auto',
    right: isLeft ? 'auto' : '20px',
    left: isLeft ? '20px' : 'auto',
    width: '64px',
    height: '64px',
    border: 'none',
    borderRadius: '32px',
    zIndex: '999999999',
    colorScheme: 'normal',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.18)',
    transition: 'width 0.25s cubic-bezier(0.4, 0, 0.2, 1), height 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-radius 0.25s ease',
    overflow: 'hidden',
    backgroundColor: 'transparent'
  });

  // Listen for resize postMessage events from iframe
  window.addEventListener('message', function (event) {
    // Verify event origin matches the widget domain
    if (baseUrl && !event.origin.startsWith(baseUrl)) return;

    const data = event.data;
    if (!data || typeof data !== 'object') return;

    if (data.type === 'TOGGLE_WIDGET') {
      if (data.isOpen) {
        // Expanded Chat Window State
        iframe.style.width = '380px';
        iframe.style.height = '600px';
        iframe.style.borderRadius = '16px';
        iframe.style.boxShadow = '0 12px 36px rgba(0, 0, 0, 0.25)';
      } else {
        // Collapsed Bubble Icon State
        iframe.style.width = '64px';
        iframe.style.height = '64px';
        iframe.style.borderRadius = '32px';
        iframe.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.18)';
      }
    }
  });

  // Inject iframe when DOM is ready
  function mount() {
    if (document.body) {
      document.body.appendChild(iframe);
    } else {
      window.addEventListener('DOMContentLoaded', function () {
        document.body.appendChild(iframe);
      });
    }
  }

  mount();
})();
