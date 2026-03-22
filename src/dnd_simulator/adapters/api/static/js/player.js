/**
 * D&D Simulator — Player interface logic.
 * WebSocket-based gameplay with REST setup phase.
 */
(() => {
    'use strict';

    // ── State ──

    let sessionId = null;
    let ws = null;
    let commandHistory = [];
    let historyIndex = -1;

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

    function escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
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
                saveSession(sid);
                connectSection.classList.add('hidden');
                chargenSection.classList.remove('hidden');
                chargenSid.textContent = sid;
            } else if (isSessionGone) {
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
        connectWebSocket();
    }

    // ── WebSocket ──

    function connectWebSocket() {
        if (ws) {
            ws.close();
            ws = null;
        }

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/api/ws/${sessionId}`;
        ws = new WebSocket(url);

        ws.onopen = () => {
            appendEventHtml('<span class="text-success">Connected to game.</span>');
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleWsMessage(msg);
        };

        ws.onclose = () => {
            appendEventHtml('<span class="text-dim">Disconnected from game.</span>');
            ws = null;
            setInputEnabled(true);
        };

        ws.onerror = () => {
            appendEventHtml('<span class="text-danger">WebSocket error.</span>');
        };
    }

    function handleWsMessage(msg) {
        switch (msg.type) {
            case 'turn':
                handleTurn(msg);
                break;
            case 'action_result':
                handleActionResult(msg);
                break;
            case 'round_result':
                handleRoundResult(msg);
                break;
            case 'error':
                appendEventHtml('<span class="text-danger">Error: ' + escapeHtml(msg.message) + '</span>');
                setInputEnabled(true);
                break;
            case 'game_over':
                appendEventHtml('<span class="text-danger">Game over.</span>');
                setInputEnabled(false);
                break;
        }
    }

    function handleTurn(msg) {
        // Update status panel from player data
        if (msg.player) updateStatus(msg.player);

        // Update perception from awareness
        updatePerceptionFromAwareness(msg.mode, msg.awareness);

        // Update combat state
        updateCombatFromAwareness(msg.mode, msg.awareness, msg.budget);

        // Update map from location data
        if (msg.location) updateMap(msg.location);

        // Show round header in combat
        if (msg.mode === 'combat' && msg.awareness && msg.awareness.round_number) {
            appendEventHtml('<span class="text-dim">--- Round ' + msg.awareness.round_number + ', your turn ---</span>');
        }

        // Show events
        showEvents(msg.events);

        // Enable input — it's the player's turn
        setInputEnabled(true);
    }

    function handleActionResult(msg) {
        if (msg.player) updateStatus(msg.player);
        showEvents(msg.events);
        // Don't re-enable input — still the player's turn, wait for next turn message
    }

    function handleRoundResult(msg) {
        if (msg.player) updateStatus(msg.player);
        if (msg.events && msg.events.length > 0) {
            appendEventHtml('<span class="text-dim">--- Others\' actions ---</span>');
        }
        showEvents(msg.events);
    }

    function showEvents(events) {
        if (!events || events.length === 0) return;
        for (const ev of events) {
            const text = ev.description || (typeof ev === 'string' ? ev : JSON.stringify(ev));
            appendEvent(text);
        }
    }

    // ── WebSocket send helpers ──

    function wsSend(msg) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(msg));
        }
    }

    function wsSendCommand(text) {
        wsSend({ type: 'command', text: text });
    }

    function setInputEnabled(enabled) {
        commandInput.disabled = !enabled;
        btnSend.disabled = !enabled;
        if (enabled) commandInput.focus();
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

    // ── Game: Perception (from turn awareness) ──

    function updatePerceptionFromAwareness(mode, awareness) {
        if (!awareness) return;

        if (mode === 'combat') {
            // In combat, show minimal perception — combat panel has the details
            let html = '<span class="text-danger">In combat</span>';
            if (awareness.self_hp !== undefined) {
                html += ` — HP: ${awareness.self_hp}/${awareness.self_max_hp}`;
            }
            perceptionBox.innerHTML = html;
            return;
        }

        // Peaceful awareness
        let html = '';

        // Time & Weather
        const hour = awareness.hour ?? 0;
        const day = awareness.day ?? 1;
        const month = awareness.month ?? 1;
        const year = awareness.year ?? 0;
        html += `<div style="font-size:0.9rem;margin-bottom:0.5rem;">`;
        html += `<strong>Y${year} M${month} D${day} ${String(hour).padStart(2,'0')}:00</strong>`;
        const w = awareness.weather;
        if (w) {
            const cond = (w.condition || '?').replace(/_/g, ' ');
            html += ` &mdash; ${escapeHtml(cond)}, ${w.temperature ?? '?'}&deg;C`;
        }
        html += `</div>`;

        // Location
        if (awareness.location_name) {
            html += `<div style="margin-bottom:0.5rem;">`;
            html += `<span class="text-success" style="font-size:1.05rem;">${escapeHtml(awareness.location_name)}</span>`;
            if (awareness.region_name) {
                html += ` <span class="text-dim">&mdash; ${escapeHtml(awareness.region_name)}</span>`;
            }
            if (awareness.territory_owner) {
                html += ` <span class="text-dim">(${escapeHtml(awareness.territory_owner)})</span>`;
            }
            html += `</div>`;
        }

        // Nearby entities
        const nearby = awareness.nearby || [];
        if (nearby.length > 0) {
            html += `<div style="margin-bottom:0.5rem;"><strong>Nearby:</strong>`;
            for (const e of nearby) {
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

        perceptionBox.innerHTML = html || '<span class="text-dim">You see nothing special.</span>';
        wireNpcActions();
    }

    function wireNpcActions() {
        perceptionBox.querySelectorAll('.npc-action').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.dataset.cmd === 'prefill') {
                    commandInput.value = btn.dataset.text;
                    commandInput.focus();
                } else {
                    sendCommand(btn.dataset.text);
                }
            });
        });
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
            const targetId = p.target_id || '?';
            const targetName = p.target_name || targetId;
            node.innerHTML = escapeHtml(targetName) +
                ' <span class="text-dim" style="font-size:0.7rem;">(' + escapeHtml(targetId) + ')</span>' +
                ' <span class="text-dim" style="font-size:0.7rem;">' + (p.distance_m || 0) + 'm</span>';
            node.addEventListener('click', () => {
                sendCommand('go ' + targetId);
            });
            pathsEl.appendChild(node);
        }
    }

    // ── Game: Combat ──

    let combatNearby = []; // current combat enemies for Attack button

    function updateCombatFromAwareness(mode, awareness, budget) {
        const exploreActions = document.getElementById('quick-actions-explore');
        const combatActions = document.getElementById('quick-actions-combat');

        if (mode !== 'combat') {
            combatPanel.classList.add('hidden');
            exploreActions.classList.remove('hidden');
            combatActions.classList.add('hidden');
            combatNearby = [];
            return;
        }

        exploreActions.classList.add('hidden');
        combatActions.classList.remove('hidden');
        combatPanel.classList.remove('hidden');

        $('#combat-round').textContent = awareness.round_number ?? '?';

        // Nearby enemies — with per-target Attack buttons
        const initEl = $('#combat-initiative');
        initEl.innerHTML = '';
        const nearby = awareness.nearby || [];
        combatNearby = nearby;
        for (const e of nearby) {
            const div = document.createElement('div');
            div.style.fontSize = '0.8rem';
            div.style.padding = '0.15rem 0';
            div.style.display = 'flex';
            div.style.alignItems = 'center';
            div.style.gap = '0.5rem';
            const desc = e.description || e.id;
            let info = escapeHtml(desc) + ' [' + escapeHtml(e.id) + ']';
            if (e.distance_ft) info += ` — ${e.distance_ft} ft`;
            if (e.direction) info += ` ${e.direction}`;
            const eid = e.id;
            div.innerHTML = `<span>${info}</span>` +
                `<button class="small danger combat-atk" data-target="${escapeHtml(eid)}" style="font-size:0.6rem;">Atk</button>`;
            initEl.appendChild(div);
        }
        // Wire per-target attack buttons
        initEl.querySelectorAll('.combat-atk').forEach(btn => {
            btn.addEventListener('click', () => {
                sendCommand('attack ' + btn.dataset.target);
            });
        });

        // Budget display
        if (budget) {
            const budgetEl = $('#combat-map');
            const parts = [];
            if (budget.actions !== undefined) parts.push(`Actions: ${budget.actions}`);
            if (budget.bonus_actions !== undefined) parts.push(`Bonus: ${budget.bonus_actions}`);
            if (budget.movement_remaining !== undefined) parts.push(`Move: ${budget.movement_remaining} ft`);
            budgetEl.textContent = parts.join(' | ');
            budgetEl.classList.remove('hidden');
        }
    }

    // Attack button — attacks closest enemy
    document.getElementById('btn-attack-target').addEventListener('click', () => {
        if (combatNearby.length > 0) {
            // Pick closest
            const sorted = [...combatNearby].sort((a, b) => (a.distance_ft || 999) - (b.distance_ft || 999));
            sendCommand('attack ' + sorted[0].id);
        }
    });

    // ── Game: Commands ──

    function sendCommand(text) {
        if (!text || !sessionId) return;

        // Add to history
        if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== text) {
            commandHistory.push(text);
        }
        historyIndex = -1;

        appendEvent('> ' + text);
        commandInput.value = '';

        // All commands are actions — disable input until next turn message
        setInputEnabled(false);
        wsSendCommand(text);
    }

    btnSend.addEventListener('click', () => {
        sendCommand(commandInput.value.trim());
    });

    commandInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            sendCommand(commandInput.value.trim());
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
            sendCommand(btn.dataset.action);
        });
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
