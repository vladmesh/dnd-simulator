/**
 * Minimal frontend i18n system.
 * Loads JSON locale files, translates strings via I18n.t(key, params),
 * and applies translations to DOM elements with data-i18n attributes.
 */
const I18n = (() => {
    'use strict';

    let locale = 'en';
    let messages = {};

    async function init(lang) {
        locale = lang || 'en';
        try {
            const resp = await fetch(`/locales/${locale}.json`);
            if (resp.ok) messages = await resp.json();
        } catch (_) {
            // Fallback: use keys as-is
        }
        applyDOM();
    }

    function t(key, params) {
        let msg = messages[key] || key;
        if (params) {
            for (const [k, v] of Object.entries(params)) {
                msg = msg.replaceAll(`{${k}}`, v);
            }
        }
        return msg;
    }

    function applyDOM(root) {
        const container = root || document;
        container.querySelectorAll('[data-i18n]').forEach(el => {
            el.textContent = t(el.dataset.i18n);
        });
        container.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            el.placeholder = t(el.dataset.i18nPlaceholder);
        });
        container.querySelectorAll('[data-i18n-title]').forEach(el => {
            el.title = t(el.dataset.i18nTitle);
        });
    }

    function getLocale() {
        return locale;
    }

    return { init, t, applyDOM, getLocale };
})();
