/**
 * D&D Simulator — Player interface logic.
 * Vanilla JS, no frameworks.
 */
(() => {
    'use strict';

    // ── State ──

    let sessionId = null;
    let commandHistory = [];
    let historyIndex = -1;
    let eventPollTimer = null;
    let lastEventCount = 0;

    // ── DOM refs ──

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const setupScreen = $('#setup-screen');
    const gameScreen = $('#game-screen');
    const connectSection = $('#connect-section');
    const chargenSection = $('#chargen-section');

    // Setup
    const sessionIdInput = $('#session-id-input');
    const worldSelect = $('#world-select');
    const btnConnect = $('#btn-connect');
    const btnNewSession = $('#btn-new-session');
    const connectError = $('#connect-error');
    const connectInfo = $('#connect-info');

    // Chargen
    const chargenSid = $('#chargen-sid');
    const btnCreateChar = $('#btn-create-char');
    const chargenError = $('#chargen-error');

    // Game
    const commandInput = $('#command-input');
    const btnSend = $('#btn-send');
    const eventLog = $('#event-log');
    const perceptionBox = $('#perception-box');
    const combatPanel = $('#combat-panel');

    // ── Helpers ──

    function showError(el, msg) {
        el.textContent = msg;
        el.classList.remove('hidden');
    }

    function hideError(el) {
        el.classList.add('hidden');
        el.textContent = '';
    }

    function showPhase(phase) {
        if (phase === 'setup') {
            setupScreen.classList.remove('hidden');
            gameScreen.classList.add('hidden');
        } else {
            setupScreen.classList.add('hidden');
            gameScreen.classList.remove('hidden');
        }
    }

    function appendEvent(text) {
        const div = document.createElement('div');
        div.className = 'event';
        div.textContent = text;
        eventLog.appendChild(div);
        eventLog.scrollTop = eventLog.scrollHeight;
    }

    function appendEventHtml(html) {
        const div = document.createElement('div');
        div.className = 'event';
        div.innerHTML = html;
        eventLog.appendChild(div);
        eventLog.scrollTop = eventLog.scrollHeight;
    }

    // ── Setup: Load worlds ──

    let worldsCache = [];

    async function loadWorlds() {
        try {
            worldsCache = await API.master.listWorlds();
            worldSelect.innerHTML = '';
            if (worldsCache.length === 0) {
                worldSelect.innerHTML = '<option value="">No worlds found</option>';
                return;
            }
            for (const w of worldsCache) {
                const opt = document.createElement('option');
                opt.value = w.id;
                opt.textContent = w.name || w.id;
                worldSelect.appendChild(opt);
            }
            updateWorldDescription();
        } catch (e) {
            worldSelect.innerHTML = '<option value="">Error loading worlds</option>';
        }
    }

    function updateWorldDescription() {
        const descEl = document.getElementById('world-description');
        const selected = worldsCache.find(w => w.id === worldSelect.value);
        descEl.textContent = selected && selected.description ? selected.description : '';
    }

    worldSelect.addEventListener('change', updateWorldDescription);

    // ── Setup: Connect ──

    btnConnect.addEventListener('click', async () => {
        const sid = sessionIdInput.value.trim();
        if (!sid) return;
        hideError(connectError);
        hideError(connectInfo);
        await tryConnect(sid);
    });

    sessionIdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') btnConnect.click();
    });

    btnNewSession.addEventListener('click', async () => {
        const worldName = worldSelect.value;
        if (!worldName) return;
        hideError(connectError);
        hideError(connectInfo);
        try {
            const res = await API.master.createSession(worldName);
            sessionIdInput.value = res.session_id;
            showError(connectInfo, 'Session created: ' + res.session_id);
            await tryConnect(res.session_id);
        } catch (e) {
            showError(connectError, e.message);
        }
    });

    async function tryConnect(sid) {
        sessionId = sid;
        try {
            const status = await API.player.getStatus(sid);
            saveSession(sid);
            enterGame(status);
        } catch (e) {
            const msg = e.message || '';
            const isNoPlayer = msg.toLowerCase().includes('no player');
            const isSessionGone = msg.toLowerCase().includes('session') && msg.toLowerCase().includes('not found');

            if (isNoPlayer) {
                // Session exists but no character yet — show chargen
                saveSession(sid);
                connectSection.classList.add('hidden');
                chargenSection.classList.remove('hidden');
                chargenSid.textContent = sid;
            } else if (isSessionGone) {
                // Session expired/server restarted — clear cache, stay on setup
                clearSavedSession();
                sessionId = null;
                showError(connectError, 'Session expired. Create or join a new one.');
            } else {
                showError(connectError, msg);
                clearSavedSession();
                sessionId = null;
            }
        }
    }

    // ── Chargen ──

    btnCreateChar.addEventListener('click', async () => {
        hideError(chargenError);
        const name = $('#char-name').value.trim();
        if (!name) {
            showError(chargenError, 'Name is required.');
            return;
        }
        const data = {
            name: name,
            race: $('#char-race').value,
            char_class: $('#char-class').value,
            level: parseInt($('#char-level').value, 10),
            alignment: $('#char-alignment').value,
            appearance: $('#char-appearance').value.trim() || undefined,
            ability_scores: {
                str: parseInt($('#char-str').value, 10),
                dex: parseInt($('#char-dex').value, 10),
                con: parseInt($('#char-con').value, 10),
                int: parseInt($('#char-int').value, 10),
                wis: parseInt($('#char-wis').value, 10),
                cha: parseInt($('#char-cha').value, 10),
            },
            hp: parseInt($('#char-hp').value, 10),
            max_hp: parseInt($('#char-hp').value, 10),
            ac: parseInt($('#char-ac').value, 10),
            gold: parseInt($('#char-gold').value, 10),
        };

        try {
            const status = await API.player.createCharacter(sessionId, data);
            enterGame(status);
        } catch (e) {
            showError(chargenError, e.message);
        }
    });

    // ── Game: Enter ──

    function enterGame(status) {
        showPhase('game');
        updateStatus(status);
        // Fetch all panels in parallel
        refreshAll();
        startEventPolling();
    }

    async function refreshAll() {
        const promises = [
            API.player.getPerception(sessionId).then(updatePerception).catch(() => {}),
            API.player.getMap(sessionId).then(updateMap).catch(() => {}),
            API.player.getCombat(sessionId).then(updateCombat).catch(() => {}),
        ];
        await Promise.allSettled(promises);
    }

    // ── Game: Status panel ──

    function updateStatus(s) {
        $('#status-name').textContent = s.name || '—';
        $('#status-race-class').textContent =
            (s.race || '?') + ' ' + (s.char_class || '?');
        $('#status-alignment').textContent = s.alignment || '';
        $('#status-level').textContent = s.level ?? '—';
        $('#status-ac').textContent = s.ac ?? '—';
        $('#status-gold').textContent = s.gold ?? '—';

        // HP
        const hp = s.hp ?? 0;
        const maxHp = s.max_hp ?? hp;
        $('#status-hp-text').textContent = hp + ' / ' + maxHp;
        const pct = maxHp > 0 ? Math.max(0, Math.min(100, (hp / maxHp) * 100)) : 0;
        const hpBar = $('#status-hp-bar');
        hpBar.style.width = pct + '%';
        if (pct <= 25) {
            hpBar.classList.add('low');
        } else {
            hpBar.classList.remove('low');
        }

        // Ability scores
        const scores = s.ability_scores || {};
        for (const ab of ['str', 'dex', 'con', 'int', 'wis', 'cha']) {
            const el = $('#stat-' + ab);
            if (el) el.textContent = scores[ab] ?? '—';
        }

        // Location
        $('#status-location').textContent = s.location_id || '—';
    }

    // ── Game: Perception ──

    function updatePerception(data) {
        if (!data) {
            perceptionBox.innerHTML = '<span class="text-dim">No perception data.</span>';
            return;
        }

        let html = '';

        // Time & Weather — single line
        const t = data.time;
        const w = data.weather;
        if (t) {
            html += `<div style="font-size:0.9rem;margin-bottom:0.5rem;">` +
                `<strong>Y${t.year} M${t.month} D${t.day} ${String(t.hour).padStart(2,'0')}:00</strong>`;
            if (w) html += ` &mdash; ${escapeHtml(w.condition || '?')}, ${w.temperature ?? '?'}&deg;C`;
            html += `</div>`;
        }

        // Current location + region
        const cur = data.current_location;
        const loc = data.location;
        if (cur || loc) {
            html += `<div style="margin-bottom:0.5rem;">`;
            if (cur) {
                html += `<span class="text-success" style="font-size:1.05rem;">${escapeHtml(cur.name || cur.id)}</span>`;
                if (cur.description) html += ` <span class="text-dim">&mdash; ${escapeHtml(cur.description)}</span>`;
                html += `<br>`;
            }
            if (loc) {
                html += `<span class="text-dim">Region: ${escapeHtml(loc.name || loc.id)} (${escapeHtml(loc.terrain || '?')})</span>`;
                if (data.territory) html += ` &mdash; <span class="text-dim">${escapeHtml(data.territory)}</span>`;
            }
            html += `</div>`;
        }

        // Entities nearby
        const entities = data.entities || [];
        if (entities.length > 0) {
            html += `<div style="margin-bottom:0.5rem;"><strong>Nearby:</strong>`;
            for (const e of entities) {
                const eid = escapeHtml(e.id);
                const desc = escapeHtml(e.description || e.id);
                html += `<div style="margin:0.3rem 0;display:flex;align-items:center;gap:0.5rem;">` +
                    `<span>${desc}</span>` +
                    `<span class="text-dim" style="font-size:0.7rem;">(${eid})</span>` +
                    `<button class="small npc-action" data-cmd="prefill" data-text="say " style="font-size:0.65rem;">Talk</button>` +
                    `<button class="small danger npc-action" data-cmd="send" data-text="attack ${eid}" style="font-size:0.65rem;">Attack</button>` +
                    `</div>`;
            }
            html += `</div>`;
        }

        // Exits
        const neighbors = data.neighbors || [];
        if (neighbors.length > 0) {
            html += `<div><strong>Exits:</strong> `;
            html += neighbors.map(n =>
                `<span class="text-success">${escapeHtml(n.name || n.target_id)}</span>` +
                ` <span class="text-dim">(${n.distance_m}m)</span>`
            ).join(', ');
            html += `</div>`;
        }

        perceptionBox.innerHTML = html || '<span class="text-dim">You see nothing special.</span>';

        // Wire up NPC action buttons
        perceptionBox.querySelectorAll('.npc-action').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.dataset.cmd === 'prefill') {
                    commandInput.value = btn.dataset.text;
                    commandInput.focus();
                } else {
                    sendAction(btn.dataset.text);
                }
            });
        });
    }

    function escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ── Game: Map ──

    function updateMap(data) {
        const currentEl = $('#map-current');
        const pathsEl = $('#map-paths');
        currentEl.textContent = data.current_location || '—';

        pathsEl.innerHTML = '';
        const paths = data.paths || [];
        if (paths.length === 0) {
            pathsEl.innerHTML = '<p class="text-dim" style="font-size:0.75rem;">No paths</p>';
            return;
        }
        for (const p of paths) {
            const node = document.createElement('div');
            node.className = 'map-node';
            const targetId = p.target_id || p.target || '?';
            const targetName = p.target_name || targetId;
            const dir = p.direction || '';
            node.innerHTML = escapeHtml(targetName) +
                ' <span class="text-dim" style="font-size:0.7rem;">(' + escapeHtml(targetId) + ')</span>' +
                (dir ? ' <span class="map-direction">[' + escapeHtml(dir) + ']</span>' : '');
            node.addEventListener('click', () => {
                sendAction('go ' + (p.target_id || p.target || targetName));
            });
            pathsEl.appendChild(node);
        }
    }

    // ── Game: Combat ──

    function updateCombat(data) {
        const exploreActions = document.getElementById('quick-actions-explore');
        const combatActions = document.getElementById('quick-actions-combat');
        if (!data || !data.in_combat) {
            combatPanel.classList.add('hidden');
            exploreActions.classList.remove('hidden');
            combatActions.classList.add('hidden');
            return;
        }
        exploreActions.classList.add('hidden');
        combatActions.classList.remove('hidden');
        combatPanel.classList.remove('hidden');
        const c = data.combat || {};
        $('#combat-round').textContent = c.round ?? '?';

        // Initiative order
        const initEl = $('#combat-initiative');
        initEl.innerHTML = '';
        const order = c.initiative_order || [];
        for (const entry of order) {
            const div = document.createElement('div');
            const name = entry.name || entry.entity_id || '?';
            const init = entry.initiative ?? '?';
            const isCurrent = entry.is_current || false;
            div.style.fontSize = '0.8rem';
            div.style.padding = '0.15rem 0';
            if (isCurrent) {
                div.innerHTML = '<strong class="text-danger">' + escapeHtml(name) + '</strong> (' + init + ')';
            } else {
                div.textContent = name + ' (' + init + ')';
            }
            initEl.appendChild(div);
        }

        // Battle map (text-based)
        const mapEl = $('#combat-map');
        if (c.battle_map) {
            mapEl.textContent = typeof c.battle_map === 'string'
                ? c.battle_map
                : JSON.stringify(c.battle_map, null, 2);
            mapEl.classList.remove('hidden');
        } else {
            mapEl.textContent = '';
            mapEl.classList.add('hidden');
        }
    }

    // ── Game: Commands ──

    async function sendAction(text) {
        if (!text || !sessionId) return;

        // Add to history
        if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== text) {
            commandHistory.push(text);
        }
        historyIndex = -1;

        appendEvent('> ' + text);
        commandInput.value = '';
        commandInput.disabled = true;
        btnSend.disabled = true;

        try {
            const result = await API.player.action(sessionId, text);
            if (result.text) {
                appendEventHtml('<span class="text-success">' + escapeHtml(result.text) + '</span>');
            }
            if (result.events && result.events.length > 0) {
                for (const ev of result.events) {
                    appendEvent(typeof ev === 'string' ? ev : JSON.stringify(ev));
                }
            }
        } catch (e) {
            appendEventHtml('<span class="text-danger">Error: ' + escapeHtml(e.message) + '</span>');
        }

        commandInput.disabled = false;
        btnSend.disabled = false;
        commandInput.focus();

        // Refresh panels
        try {
            const [status, _, __, ___] = await Promise.allSettled([
                API.player.getStatus(sessionId),
                API.player.getPerception(sessionId).then(updatePerception),
                API.player.getMap(sessionId).then(updateMap),
                API.player.getCombat(sessionId).then(updateCombat),
            ]);
            if (status.status === 'fulfilled') updateStatus(status.value);
        } catch (_) {}
    }

    btnSend.addEventListener('click', () => {
        sendAction(commandInput.value.trim());
    });

    commandInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            sendAction(commandInput.value.trim());
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (commandHistory.length === 0) return;
            if (historyIndex === -1) {
                historyIndex = commandHistory.length - 1;
            } else if (historyIndex > 0) {
                historyIndex--;
            }
            commandInput.value = commandHistory[historyIndex];
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (historyIndex === -1) return;
            if (historyIndex < commandHistory.length - 1) {
                historyIndex++;
                commandInput.value = commandHistory[historyIndex];
            } else {
                historyIndex = -1;
                commandInput.value = '';
            }
        }
    });

    // Quick action buttons
    for (const btn of $$('[data-action]')) {
        btn.addEventListener('click', () => {
            sendAction(btn.dataset.action);
        });
    }

    // ── Event polling ──

    function startEventPolling() {
        if (eventPollTimer) clearInterval(eventPollTimer);
        eventPollTimer = setInterval(pollEvents, 3000);
    }

    async function pollEvents() {
        if (!sessionId) return;
        try {
            const data = await API.player.getEvents(sessionId);
            const events = data.events || [];
            // Only show new events since last poll
            if (events.length > lastEventCount) {
                const newEvents = events.slice(lastEventCount);
                for (const ev of newEvents) {
                    const text = typeof ev === 'string' ? ev : (ev.text || ev.message || JSON.stringify(ev));
                    appendEvent(text);
                }
                lastEventCount = events.length;
            }
        } catch (_) {}

        // Also refresh combat state
        try {
            const combatData = await API.player.getCombat(sessionId);
            updateCombat(combatData);
        } catch (_) {}
    }

    // ── Session persistence ──

    function saveSession(sid) {
        try { localStorage.setItem('dnd_session_id', sid); } catch (_) {}
    }

    function clearSavedSession() {
        try { localStorage.removeItem('dnd_session_id'); } catch (_) {}
    }

    function getSavedSession() {
        try { return localStorage.getItem('dnd_session_id'); } catch (_) { return null; }
    }

    // ── Init ──

    showPhase('setup');
    loadWorlds();

    // Auto-reconnect if we have a saved session
    const savedSid = getSavedSession();
    if (savedSid) {
        sessionIdInput.value = savedSid;
        tryConnect(savedSid);
    }

})();
