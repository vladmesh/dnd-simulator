/**
 * D&D Simulator — Master Panel logic.
 * Two distinct modes: Template view (read-only) and Session view (live, editable).
 */
(() => {
    'use strict';

    // ── I18n init ──

    function detectLang() {
        const saved = localStorage.getItem('dnd_lang');
        if (saved) return saved;
        const nav = (navigator.language || '').toLowerCase();
        if (nav.startsWith('ru')) return 'ru';
        return 'en';
    }

    function currentLang() {
        return localStorage.getItem('dnd_lang') || 'en';
    }

    function setActiveLangFlags(lang) {
        document.querySelectorAll('.lang-flag').forEach(el => {
            el.classList.toggle('active', el.dataset.lang === lang);
        });
    }

    const initLang = detectLang();
    localStorage.setItem('dnd_lang', initLang);
    setActiveLangFlags(initLang);
    I18n.init(initLang).then(() => {
        document.title = I18n.t('master.title');
    });

    document.querySelectorAll('.lang-flag').forEach(el => {
        el.addEventListener('click', () => {
            const lang = el.dataset.lang;
            localStorage.setItem('dnd_lang', lang);
            setActiveLangFlags(lang);
            I18n.init(lang).then(() => {
                document.title = I18n.t('master.title');
                loadWorlds(); // reload world names in new language
            });
        });
    });

    // ── State ──
    let sessionsList = [];
    let currentSession = null;    // active session id
    let currentTemplate = null;   // active template id being viewed
    let currentTemplateData = null; // cached template data for editing
    let activeMode = null;        // 'template' | 'session' | null
    let refreshTimer = null;
    let worldsList = [];          // cached worlds for session creation dialog

    // ── DOM refs ──
    const $ = (id) => document.getElementById(id);

    const $worldsList     = $('worlds-list');
    const $sessionsList   = $('sessions-list');
    const $noSelection    = $('no-selection');
    const $templatePanel  = $('template-panel');
    const $sessionPanel   = $('session-panel');
    const $sessionIdLabel = $('session-id-label');

    // Template view
    const $templateName   = $('template-name');
    const $templateDesc   = $('template-description');

    // Session: Overview
    const $overviewTime      = $('overview-time');
    const $regionsTbody      = $('regions-tbody');
    const $nationsTbody      = $('nations-tbody');
    const $settlementsTbody  = $('settlements-tbody');

    // Session: Entities
    const $creaturesTbody   = $('creatures-tbody');
    const $creaturesFilter  = $('creatures-filter');
    const $spawnForm        = $('spawn-form');
    const $spawnMsg         = $('spawn-msg');
    const $creatureEditPanel = $('creature-edit-panel');
    const $editMsg          = $('edit-msg');

    // Session: Time
    const $timeDisplay    = $('time-display');
    const $timeMsg        = $('time-msg');

    // Session: Save/Load
    const $saveMsg        = $('save-msg');
    const $savesList      = $('saves-list');

    // New Session Dialog
    const $newSessionDialog = $('new-session-dialog');
    const $newSessionWorld  = $('new-session-world');
    const $newSessionMsg    = $('new-session-msg');

    // ── Helpers ──
    function show(el) { el.classList.remove('hidden'); }
    function hide(el) { el.classList.add('hidden'); }
    function flashMsg(el, text, cls) {
        el.textContent = text;
        el.className = cls + ' mt-1';
        setTimeout(() => { el.textContent = ''; }, 4000);
    }
    function hpBar(hp, maxHp) {
        const pct = maxHp > 0 ? Math.round((hp / maxHp) * 100) : 0;
        const low = pct <= 30 ? ' low' : '';
        return `<div class="hp-bar-outer" style="width:60px;display:inline-block;vertical-align:middle;">` +
               `<div class="hp-bar-inner${low}" style="width:${pct}%"></div></div> ${hp}/${maxHp}`;
    }
    function esc(str) {
        if (str == null) return '';
        const d = document.createElement('div');
        d.textContent = String(str);
        return d.innerHTML;
    }
    function typeLabel(entityType) {
        if (entityType === 'player') return '<span style="color:#6bb5ff">' + esc(I18n.t('entity.player')) + '</span>';
        if (entityType === 'npc') return '<span style="color:#e94560">' + esc(I18n.t('entity.npc')) + '</span>';
        return '<span style="color:#aaa">' + esc(I18n.t('entity.monster')) + '</span>';
    }

    // ── Mode switching ──
    function setMode(mode) {
        activeMode = mode;
        hide($noSelection);
        hide($templatePanel);
        hide($sessionPanel);
        if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }

        if (mode === 'template') show($templatePanel);
        else if (mode === 'session') show($sessionPanel);
        else show($noSelection);
    }

    // ════════════════════════════════════
    // WORLD TEMPLATES
    // ════════════════════════════════════

    async function loadWorlds() {
        try {
            worldsList = await API.master.listWorlds(currentLang());
            if (!worldsList.length) {
                $worldsList.textContent = I18n.t('master.no_worlds');
                return;
            }
            $worldsList.innerHTML = '';
            worldsList.forEach(w => {
                const card = document.createElement('div');
                card.className = 'card' + (currentTemplate === w.id ? ' active' : '');
                card.innerHTML = `<strong>${esc(w.name)}</strong>` +
                    (w.description ? `<br><span class="text-dim" style="font-size:0.8rem;">${esc(w.description).substring(0, 80)}</span>` : '');
                card.addEventListener('click', () => viewTemplate(w.id));
                $worldsList.appendChild(card);
            });
        } catch (err) {
            $worldsList.textContent = I18n.t('error.prefix', { message: err.message });
        }
    }

    async function viewTemplate(worldId) {
        currentTemplate = worldId;
        currentSession = null;
        setMode('template');
        renderSessionsList(); // re-render to clear active state
        loadWorlds(); // re-render to update active state

        try {
            const data = await API.master.getWorldTemplate(worldId);
            currentTemplateData = data;
            $templateName.textContent = data.name || worldId;
            $templateDesc.textContent = data.description || '';
            renderTemplateData(data);
        } catch (err) {
            $templateName.textContent = worldId;
            $templateDesc.textContent = I18n.t('error.loading', { message: err.message });
        }
    }

    function renderTemplateData(data) {
        // Regions
        const rTbody = $('tpl-regions-tbody');
        rTbody.innerHTML = '';
        (data.regions || []).forEach(r => {
            const conns = (r.connections || []).map(c => `${c.target} (${c.direction})`).join(', ') || '—';
            rTbody.innerHTML += `<tr><td>${esc(r.id)}</td><td>${esc(r.name)}</td><td>${esc(r.terrain)}</td>` +
                `<td>${r.latitude}</td><td>${r.longitude}</td><td>${r.elevation}</td>` +
                `<td>${r.water_proximity}</td><td class="text-dim">${esc(conns)}</td></tr>`;
        });

        // Settlements
        const sTbody = $('tpl-settlements-tbody');
        sTbody.innerHTML = '';
        (data.settlements || []).forEach(s => {
            sTbody.innerHTML += `<tr><td>${esc(s.id)}</td><td>${esc(s.name)}</td><td class="text-dim">${esc(s.region_id)}</td>` +
                `<td>${esc(s.type)}</td><td>${s.population}</td><td>${s.prosperity}</td><td>${s.defenses}</td></tr>`;
        });

        // Locations
        const lTbody = $('tpl-locations-tbody');
        lTbody.innerHTML = '';
        (data.locations || []).forEach(loc => {
            const neighbors = (loc.neighbors || []).map(n => `${n.target} (${n.distance}m)`).join(', ') || '—';
            lTbody.innerHTML += `<tr><td>${esc(loc.id)}</td><td>${esc(loc.name)}</td>` +
                `<td class="text-dim">${esc(loc.region_id)}</td><td class="text-dim">${esc(loc.settlement_id || '—')}</td>` +
                `<td class="text-dim">${esc(neighbors)}</td></tr>`;
        });

        // Nations
        const nTbody = $('tpl-nations-tbody');
        nTbody.innerHTML = '';
        (data.nations || []).forEach(n => {
            const leader = n.leader ? `${n.leader.name}, ${n.leader.age}, ${n.leader.trait}` : '—';
            nTbody.innerHTML += `<tr><td>${esc(n.id)}</td><td>${esc(n.name)}</td>` +
                `<td class="text-dim">${esc((n.regions || []).join(', '))}</td>` +
                `<td>${n.wealth}</td><td>${n.military}</td><td>${n.stability}</td>` +
                `<td class="text-dim">${esc(leader)}</td></tr>`;
        });

        // NPCs
        const npTbody = $('tpl-npcs-tbody');
        npTbody.innerHTML = '';
        (data.npcs || []).forEach(npc => {
            npTbody.innerHTML += `<tr><td>${esc(npc.id)}</td><td>${esc(npc.name)}</td>` +
                `<td>${esc(npc.role)}</td><td class="text-dim">${esc(npc.location_id)}</td>` +
                `<td>${esc(npc.race)}</td><td>${esc(npc.char_class)}</td>` +
                `<td>${npc.hp}</td><td>${npc.ac}</td><td>${esc(npc.ai_type)}</td></tr>`;
        });
    }

    // Template tabs
    $('template-tabs').addEventListener('click', (e) => {
        const tab = e.target.closest('.tab');
        if (!tab) return;
        $('template-tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        $templatePanel.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
        tab.classList.add('active');
        $('tab-' + tab.dataset.tab).classList.add('active');
    });

    // ════════════════════════════════════
    // SESSIONS
    // ════════════════════════════════════

    // -- New Session Dialog --

    $('btn-new-session').addEventListener('click', () => {
        $newSessionWorld.innerHTML = '';
        worldsList.forEach(w => {
            const opt = document.createElement('option');
            opt.value = w.id;
            opt.textContent = `${w.name} (${w.id})`;
            $newSessionWorld.appendChild(opt);
        });
        $newSessionMsg.textContent = '';
        show($newSessionDialog);
    });

    $('btn-cancel-new-session').addEventListener('click', () => hide($newSessionDialog));

    $('btn-confirm-new-session').addEventListener('click', async () => {
        const worldId = $newSessionWorld.value;
        const lang = currentLang();
        if (!worldId) { $newSessionMsg.textContent = I18n.t('dialog.select_world'); return; }
        try {
            const res = await API.master.createSession(worldId, lang);
            hide($newSessionDialog);
            await loadSessions();
            selectSession(res.session_id);
        } catch (err) {
            $newSessionMsg.textContent = I18n.t('error.prefix', { message: err.message });
        }
    });

    // -- Session list --

    async function loadSessions() {
        try {
            sessionsList = await API.master.listSessions();
            renderSessionsList();
        } catch (err) {
            $sessionsList.textContent = I18n.t('error.prefix', { message: err.message });
        }
    }

    function renderSessionsList() {
        if (sessionsList.length === 0) {
            $sessionsList.innerHTML = '<span class="text-dim">' + esc(I18n.t('master.no_sessions')) + '</span>';
            return;
        }
        $sessionsList.innerHTML = '';
        sessionsList.forEach(s => {
            const card = document.createElement('div');
            card.className = 'card' + (s.session_id === currentSession ? ' active' : '');
            card.innerHTML = `<strong>${esc(s.session_id)}</strong>` +
                (s.player_name ? ` <span class="text-dim">${esc(s.player_name)}</span>` : '');
            card.addEventListener('click', () => selectSession(s.session_id));
            $sessionsList.appendChild(card);
        });
    }

    function selectSession(sid) {
        currentSession = sid;
        currentTemplate = null;
        $sessionIdLabel.textContent = sid;
        setMode('session');
        renderSessionsList();
        loadWorlds(); // clear template active state
        refreshSession();

        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(refreshSession, 5000);
    }

    async function deleteCurrentSession() {
        if (!currentSession) return;
        if (!confirm(I18n.t('confirm.delete_session', { id: currentSession }))) return;
        try {
            await API.master.deleteSession(currentSession);
            currentSession = null;
            setMode(null);
            await loadSessions();
        } catch (err) {
            alert(I18n.t('error.delete_failed', { message: err.message }));
        }
    }

    // -- Refresh session data --

    async function refreshSession() {
        if (!currentSession) return;
        try {
            const filterType = $creaturesFilter.value || undefined;
            const [state, creatures] = await Promise.all([
                API.master.getSession(currentSession),
                API.master.listCreatures(currentSession, { entity_type: filterType }),
            ]);
            renderOverview(state);
            renderCreatures(creatures);
            renderTime(state.time);
        } catch (err) {
            console.error('Refresh error:', err);
        }
    }

    // -- Overview --

    function renderOverview(state) {
        $overviewTime.textContent = state.time || '—';

        $regionsTbody.innerHTML = '';
        (state.regions || []).forEach(r => {
            const weather = r.weather ? `${r.weather.condition}, ${r.weather.temperature}°C` : '—';
            $regionsTbody.innerHTML += `<tr><td>${esc(r.name || r.id)}</td><td>${esc(r.terrain || '—')}</td><td>${esc(weather)}</td></tr>`;
        });

        $nationsTbody.innerHTML = '';
        (state.nations || []).forEach(n => {
            const tr = document.createElement('tr');
            tr.dataset.id = n.id || n.name;
            tr.innerHTML =
                `<td>${esc(n.name || n.id)}</td>` +
                `<td class="editable" data-field="wealth">${n.wealth ?? '—'}</td>` +
                `<td class="editable" data-field="military">${n.military ?? '—'}</td>` +
                `<td class="editable" data-field="stability">${n.stability ?? '—'}</td>` +
                `<td><button class="small btn-edit-nation">${esc(I18n.t('master.edit'))}</button></td>`;
            $nationsTbody.appendChild(tr);
        });

        $settlementsTbody.innerHTML = '';
        (state.settlements || []).forEach(s => {
            const tr = document.createElement('tr');
            tr.dataset.id = s.id || s.name;
            tr.innerHTML =
                `<td>${esc(s.name || s.id)}</td>` +
                `<td>${esc(s.type || '—')}</td>` +
                `<td class="editable" data-field="population">${s.population ?? '—'}</td>` +
                `<td class="editable" data-field="prosperity">${s.prosperity ?? '—'}</td>` +
                `<td class="editable" data-field="defenses">${s.defenses ?? '—'}</td>` +
                `<td><button class="small btn-edit-settlement">${esc(I18n.t('master.edit'))}</button></td>`;
            $settlementsTbody.appendChild(tr);
        });
    }

    // -- Inline edit: Nations --

    $nationsTbody.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-edit-nation');
        if (!btn) return;
        const tr = btn.closest('tr');
        const nationId = tr.dataset.id;
        const cells = tr.querySelectorAll('.editable');

        if (btn.dataset.editing === 'true') {
            const data = {};
            cells.forEach(td => {
                const input = td.querySelector('input');
                if (input) {
                    const val = parseFloat(input.value);
                    if (!isNaN(val)) data[td.dataset.field] = val;
                }
            });
            API.master.patchNation(currentSession, nationId, data)
                .then(() => refreshSession())
                .catch(err => alert(I18n.t('error.patch_nation', { message: err.message })));
            return;
        }

        cells.forEach(td => {
            const val = td.textContent;
            td.innerHTML = `<input type="number" value="${val === '—' ? '' : val}" style="width:70px">`;
        });
        btn.textContent = I18n.t('save.btn');
        btn.dataset.editing = 'true';
        btn.classList.add('primary');
    });

    // -- Inline edit: Settlements --

    $settlementsTbody.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-edit-settlement');
        if (!btn) return;
        const tr = btn.closest('tr');
        const settId = tr.dataset.id;
        const cells = tr.querySelectorAll('.editable');

        if (btn.dataset.editing === 'true') {
            const data = {};
            cells.forEach(td => {
                const input = td.querySelector('input');
                if (input) {
                    const val = parseFloat(input.value);
                    if (!isNaN(val)) data[td.dataset.field] = val;
                }
            });
            API.master.patchSettlement(currentSession, settId, data)
                .then(() => refreshSession())
                .catch(err => alert(I18n.t('error.patch_settlement', { message: err.message })));
            return;
        }

        cells.forEach(td => {
            const val = td.textContent;
            td.innerHTML = `<input type="number" value="${val === '—' ? '' : val}" style="width:70px">`;
        });
        btn.textContent = I18n.t('save.btn');
        btn.dataset.editing = 'true';
        btn.classList.add('primary');
    });

    // -- Creatures --

    $creaturesFilter.addEventListener('change', refreshSession);

    function renderCreatures(creatures) {
        $creaturesTbody.innerHTML = '';
        (Array.isArray(creatures) ? creatures : []).forEach(c => {
            const isPlayer = c.entity_type === 'player';
            const actions = isPlayer
                ? `<button class="small btn-view-creature" data-id="${esc(c.id)}">${esc(I18n.t('entity.view'))}</button>`
                : `<button class="small btn-edit-creature" data-id="${esc(c.id)}">${esc(I18n.t('entity.edit'))}</button> ` +
                  `<button class="small danger btn-del-creature" data-id="${esc(c.id)}">${esc(I18n.t('entity.del'))}</button>`;

            $creaturesTbody.innerHTML +=
                `<tr>` +
                `<td>${typeLabel(c.entity_type)}</td>` +
                `<td>${esc(c.name)}</td>` +
                `<td class="text-dim">${esc(c.location_id || '—')}</td>` +
                `<td>${esc(c.role || '—')}</td>` +
                `<td>${hpBar(c.hp ?? 0, c.max_hp ?? 0)}</td>` +
                `<td>${c.ac ?? '—'}</td>` +
                `<td>${esc(c.ai_type || '—')}</td>` +
                `<td>${c.active ? '<span class="text-success">' + esc(I18n.t('entity.yes')) + '</span>' : '<span class="text-danger">' + esc(I18n.t('entity.no')) + '</span>'}</td>` +
                `<td>${actions}</td>` +
                `</tr>`;
        });
    }

    $creaturesTbody.addEventListener('click', async (e) => {
        const editBtn = e.target.closest('.btn-edit-creature');
        const viewBtn = e.target.closest('.btn-view-creature');
        const delBtn  = e.target.closest('.btn-del-creature');

        if (editBtn || viewBtn) {
            const eid = (editBtn || viewBtn).dataset.id;
            try {
                const creature = await API.master.getCreature(currentSession, eid);
                openCreatureEdit(creature);
            } catch (err) { alert(I18n.t('error.load_creature', { message: err.message })); }
        }
        if (delBtn) {
            if (!confirm(I18n.t('confirm.delete_creature', { id: delBtn.dataset.id }))) return;
            try {
                await API.master.deleteCreature(currentSession, delBtn.dataset.id);
                hide($creatureEditPanel);
                refreshSession();
            } catch (err) { alert(I18n.t('error.delete_failed', { message: err.message })); }
        }
    });

    function openCreatureEdit(creature) {
        const isPlayer = creature.entity_type === 'player';
        const isNpc = creature.entity_type === 'npc';

        $('edit-creature-id').value = creature.id;
        $('edit-creature-type').value = creature.entity_type || '';
        $('edit-creature-name').textContent = creature.name;
        $('edit-hp').value = creature.hp ?? '';
        $('edit-ac').value = creature.ac ?? '';
        $('edit-gold').value = creature.gold ?? '';
        $('edit-location').value = creature.location_id || '';
        $('edit-personality').value = creature.personality || '';
        $('edit-brain-type').value = creature.ai_type || 'rule_based';
        $('edit-brain-model').value = '';
        $editMsg.textContent = '';

        // Show/hide NPC-specific fields
        if (isNpc) show($('edit-npc-fields'));
        else hide($('edit-npc-fields'));

        // Player: read-only
        if (isPlayer) {
            show($('edit-readonly-notice'));
            hide($('edit-creature-fields'));
        } else {
            hide($('edit-readonly-notice'));
            show($('edit-creature-fields'));
        }

        show($creatureEditPanel);
    }

    $('btn-close-edit').addEventListener('click', () => hide($creatureEditPanel));

    $('btn-save-creature').addEventListener('click', async () => {
        const eid = $('edit-creature-id').value;
        const data = {};
        const hp = parseInt($('edit-hp').value);
        const ac = parseInt($('edit-ac').value);
        const gold = parseInt($('edit-gold').value);
        const personality = $('edit-personality').value.trim();
        const locationId  = $('edit-location').value.trim();
        if (!isNaN(hp))  data.current_hp = hp;
        if (!isNaN(ac))  data.ac = ac;
        if (!isNaN(gold)) data.gold = gold;
        if (personality)  data.personality = personality;
        if (locationId)   data.location_id = locationId;
        try {
            await API.master.patchCreature(currentSession, eid, data);
            flashMsg($editMsg, I18n.t('edit.saved'), 'text-success');
            refreshSession();
        } catch (err) { flashMsg($editMsg, I18n.t('error.prefix', { message: err.message }), 'text-danger'); }
    });

    $('btn-save-brain').addEventListener('click', async () => {
        const eid = $('edit-creature-id').value;
        const type  = $('edit-brain-type').value;
        const model = $('edit-brain-model').value.trim() || null;
        try {
            await API.master.setBrain(currentSession, eid, type, model);
            flashMsg($editMsg, I18n.t('edit.brain_updated'), 'text-success');
            refreshSession();
        } catch (err) { flashMsg($editMsg, I18n.t('error.prefix', { message: err.message }), 'text-danger'); }
    });

    // -- Spawn --

    $('btn-show-spawn').addEventListener('click', () => { show($spawnForm); $spawnMsg.textContent = ''; });
    $('btn-cancel-spawn').addEventListener('click', () => hide($spawnForm));

    // Toggle NPC-specific fields based on spawn type
    $('spawn-type').addEventListener('change', () => {
        const isNpc = $('spawn-type').value === 'npc';
        if (isNpc) show($('spawn-npc-fields'));
        else hide($('spawn-npc-fields'));
    });

    $('btn-spawn').addEventListener('click', async () => {
        const entityType = $('spawn-type').value;
        const data = {
            id:             $('spawn-id').value.trim(),
            name:           $('spawn-name').value.trim(),
            entity_type:    entityType,
            region_id:      $('spawn-region').value.trim(),
            start_location: $('spawn-location').value.trim(),
            hp:             parseInt($('spawn-hp').value) || 10,
            ac:             parseInt($('spawn-ac').value) || 12,
            ai:             $('spawn-ai').value,
        };
        if (entityType === 'npc') {
            data.role        = $('spawn-role').value.trim();
            data.personality = $('spawn-personality').value.trim();
        }
        if (!data.id || !data.name) {
            flashMsg($spawnMsg, I18n.t('spawn.id_name_required'), 'text-danger');
            return;
        }
        try {
            await API.master.spawnCreature(currentSession, data);
            flashMsg($spawnMsg, I18n.t('spawn.spawned'), 'text-success');
            hide($spawnForm);
            refreshSession();
        } catch (err) { flashMsg($spawnMsg, I18n.t('error.prefix', { message: err.message }), 'text-danger'); }
    });

    // -- Time Tab --

    function renderTime(timeStr) {
        $timeDisplay.textContent = timeStr || '—';
        $overviewTime.textContent = timeStr || '—';
    }

    document.querySelectorAll('[data-hours]').forEach(btn => {
        btn.addEventListener('click', () => advanceTime(parseInt(btn.dataset.hours)));
    });

    $('btn-advance-custom').addEventListener('click', () => {
        const hours = parseInt($('custom-hours').value);
        if (hours > 0) advanceTime(hours);
    });

    async function advanceTime(hours) {
        $timeMsg.textContent = '';
        try {
            const res = await API.master.advanceTime(currentSession, hours);
            flashMsg($timeMsg, res.message || I18n.t('time.advanced', { hours: hours }), 'text-success');
            refreshSession();
        } catch (err) { flashMsg($timeMsg, I18n.t('error.prefix', { message: err.message }), 'text-danger'); }
    }

    // -- Save / Load --

    $('btn-save').addEventListener('click', async () => {
        const name = $('save-name').value.trim() || null;
        try {
            const res = await API.master.save(currentSession, name);
            flashMsg($saveMsg, res.message || I18n.t('save.saved'), 'text-success');
            loadSavesList();
        } catch (err) { flashMsg($saveMsg, I18n.t('error.prefix', { message: err.message }), 'text-danger'); }
    });

    async function loadSavesList() {
        if (!currentSession) return;
        try {
            const res = await API.master.listSaves(currentSession);
            const saves = res.saves || [];
            if (!saves.length) { $savesList.innerHTML = '<span class="text-dim">' + esc(I18n.t('load.no_saves')) + '</span>'; return; }
            $savesList.innerHTML = '';
            saves.forEach(s => {
                const name = typeof s === 'string' ? s : s.name || s;
                const row = document.createElement('div');
                row.className = 'flex items-center justify-between';
                row.style.cssText = 'padding:0.3rem 0;border-bottom:1px solid var(--border);';
                row.innerHTML = `<span>${esc(String(name))}</span>` +
                    `<button class="small primary btn-load-save" data-name="${esc(String(name))}">${esc(I18n.t('load.btn'))}</button>`;
                $savesList.appendChild(row);
            });
        } catch (err) { $savesList.textContent = I18n.t('error.prefix', { message: err.message }); }
    }

    $savesList.addEventListener('click', async (e) => {
        const btn = e.target.closest('.btn-load-save');
        if (!btn) return;
        if (!confirm(I18n.t('load.confirm', { name: btn.dataset.name }))) return;
        try {
            await API.master.load(currentSession, btn.dataset.name);
            refreshSession();
        } catch (err) { alert(I18n.t('load.failed', { message: err.message })); }
    });

    // -- Session Tabs --

    $('session-tabs').addEventListener('click', (e) => {
        const tab = e.target.closest('.tab');
        if (!tab) return;
        $('session-tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        $sessionPanel.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
        tab.classList.add('active');
        $('tab-' + tab.dataset.tab).classList.add('active');
        if (tab.dataset.tab === 'saveload') loadSavesList();
    });

    // -- Delete Session --
    $('btn-delete-session').addEventListener('click', deleteCurrentSession);

    // ════════════════════════════════════
    // WORLD BUILDER
    // ════════════════════════════════════

    $('btn-new-world').addEventListener('click', () => {
        WorldBuilder.onCreated = () => loadWorlds();
        WorldBuilder.open();
    });

    $('btn-edit-template').addEventListener('click', () => {
        if (!currentTemplateData) return;
        WorldBuilder.onCreated = () => {
            loadWorlds();
            viewTemplate(currentTemplate);
        };
        WorldBuilder.openForEdit(currentTemplateData);
    });

    // ════════════════════════════════════
    // INIT
    // ════════════════════════════════════

    loadWorlds();
    loadSessions();
})();
