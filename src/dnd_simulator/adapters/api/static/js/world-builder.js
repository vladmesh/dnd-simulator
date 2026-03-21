/**
 * D&D Simulator — World Builder wizard module.
 * Self-contained 7-step wizard for creating worlds via the debug UI.
 * Uses API.master.createWorld() from api.js.
 */
const WorldBuilder = (() => {
    'use strict';

    // ── Constants ──

    const TERRAINS = ['plains', 'forest', 'hills', 'mountains', 'desert', 'swamp', 'coast', 'tundra'];
    const DIRECTIONS = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'];
    const SETTLEMENT_TYPES = ['village', 'town', 'city'];
    const RACES = ['human', 'elf', 'dwarf', 'halfling', 'gnome', 'half_elf', 'half_orc', 'tiefling', 'dragonborn'];
    const CLASSES = [
        'commoner', 'fighter', 'wizard', 'rogue', 'cleric', 'ranger',
        'paladin', 'barbarian', 'bard', 'druid', 'monk', 'sorcerer', 'warlock',
    ];
    const ABILITIES = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
    const DAMAGE_TYPES = [
        'slashing', 'piercing', 'bludgeoning', 'fire', 'cold', 'lightning',
        'thunder', 'acid', 'poison', 'radiant', 'necrotic', 'force', 'psychic',
    ];
    const LEADER_TRAITS = ['militarist', 'merchant', 'diplomat'];

    const STEP_LABELS = ['World', 'Regions', 'Settlements', 'Locations', 'Nations', 'NPCs', 'Review'];
    const TOTAL_STEPS = STEP_LABELS.length;

    // ── State ──

    let overlay = null;
    let currentStep = 0;
    let worldData = null;
    let editingItem = null; // { type, id } when editing an existing item
    let editMode = false;   // true when editing an existing world template

    // ── Public callback ──

    let onCreated = null;

    // ── Helpers ──

    function slugify(str) {
        return str.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    }

    function esc(str) {
        if (str == null) return '';
        const d = document.createElement('div');
        d.textContent = String(str);
        return d.innerHTML;
    }

    function el(tag, attrs, children) {
        const e = document.createElement(tag);
        if (attrs) {
            Object.keys(attrs).forEach(k => {
                if (k === 'className') e.className = attrs[k];
                else if (k === 'style' && typeof attrs[k] === 'object') Object.assign(e.style, attrs[k]);
                else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
                else e.setAttribute(k, attrs[k]);
            });
        }
        if (children != null) {
            if (typeof children === 'string') e.innerHTML = children;
            else if (Array.isArray(children)) children.forEach(c => { if (c) e.appendChild(c); });
            else e.appendChild(children);
        }
        return e;
    }

    function selectOptions(list, selected) {
        return list.map(v =>
            `<option value="${esc(v)}"${v === selected ? ' selected' : ''}>${esc(v)}</option>`
        ).join('');
    }

    function resetWizard() {
        currentStep = 0;
        editingItem = null;
        editMode = false;
        worldData = {
            id: '', name: '', description: '',
            regions: {},
            locations: {},
            nations: {},
            npcs: {},
        };
    }

    /**
     * Convert template API response → worldData format for the builder.
     * Template API returns flat arrays; worldData nests settlements under regions.
     */
    function templateToWorldData(tpl) {
        const wd = {
            id: tpl.id || '',
            name: tpl.name || '',
            description: tpl.description || '',
            regions: {},
            locations: {},
            nations: {},
            npcs: {},
        };

        // Regions
        (tpl.regions || []).forEach(r => {
            wd.regions[r.id] = {
                name: r.name,
                terrain: r.terrain,
                latitude: r.latitude ?? 45.0,
                longitude: r.longitude ?? 0.0,
                elevation: r.elevation ?? 100,
                water_proximity: r.water_proximity ?? 0.0,
                connections: (r.connections || []).map(c => ({ target: c.target, direction: c.direction })),
                settlements: [],
            };
        });

        // Settlements → nest under their region
        (tpl.settlements || []).forEach(s => {
            const rid = s.region_id;
            if (wd.regions[rid]) {
                wd.regions[rid].settlements.push({
                    id: s.id,
                    name: s.name,
                    type: s.type || 'village',
                    population: s.population ?? 200,
                    prosperity: s.prosperity ?? 50,
                    defenses: s.defenses ?? 20,
                });
            }
        });

        // Locations
        (tpl.locations || []).forEach(loc => {
            wd.locations[loc.id] = {
                name: loc.name,
                region: loc.region_id || '',
                settlement: loc.settlement_id || '',
                description: loc.description || '',
                neighbors: (loc.neighbors || []).map(n => ({ target: n.target, distance: n.distance })),
            };
        });

        // Nations
        (tpl.nations || []).forEach(n => {
            wd.nations[n.id] = {
                name: n.name,
                regions: n.regions || [],
                wealth: n.wealth ?? 50,
                military: n.military ?? 50,
                stability: n.stability ?? 70,
                leader: n.leader ? {
                    name: n.leader.name || '',
                    age: n.leader.age ?? 40,
                    trait: n.leader.trait || 'merchant',
                } : { name: '', age: 40, trait: 'merchant' },
            };
        });

        // NPCs
        (tpl.npcs || []).forEach(npc => {
            wd.npcs[npc.id] = {
                name: npc.name,
                role: npc.role || '',
                personality: npc.personality || '',
                settlement_id: npc.settlement_id || '',
                start_location: npc.location_id || '',
                race: npc.race || 'human',
                class: npc.char_class || 'commoner',
                hp: npc.hp ?? 18,
                ac: npc.ac ?? 12,
                speed: 30,
                ability_scores: {},
                ai: npc.ai_type || 'rule_based',
                attacks: [],
            };
        });

        return wd;
    }

    // ── Overlay DOM ──

    function createOverlay() {
        overlay = el('div', {
            id: 'world-builder-overlay',
            style: {
                position: 'fixed', top: '0', left: '0',
                width: '100%', height: '100%',
                background: 'rgba(0,0,0,0.85)',
                zIndex: '1000',
                display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
                paddingTop: '3vh',
            },
        });

        const container = el('div', {
            className: 'panel',
            style: {
                width: '100%', maxWidth: '800px',
                maxHeight: '90vh', overflowY: 'auto',
                position: 'relative',
            },
        });

        // Close button
        const closeBtn = el('button', {
            className: 'small danger',
            style: { position: 'absolute', top: '0.75rem', right: '0.75rem' },
            onClick: close,
        }, 'X');
        container.appendChild(closeBtn);

        // Title
        container.appendChild(el('h2', { id: 'wb-title', style: { marginBottom: '1rem' } }, 'Create New World'));

        // Step indicators
        const stepsBar = el('div', {
            id: 'wb-steps-bar',
            style: {
                display: 'flex', justifyContent: 'center', gap: '0.5rem',
                marginBottom: '1.5rem', flexWrap: 'wrap',
            },
        });
        STEP_LABELS.forEach((label, i) => {
            const circle = el('div', {
                className: 'wb-step-indicator',
                'data-step': String(i),
                style: {
                    width: '32px', height: '32px', borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: '2px solid var(--border)', cursor: 'pointer',
                    fontSize: '0.8rem', fontWeight: '600',
                    transition: 'all 0.2s',
                },
                title: label,
                onClick: () => goToStep(i),
            }, String(i + 1));
            stepsBar.appendChild(circle);
        });
        container.appendChild(stepsBar);

        // Step label
        container.appendChild(el('h3', { id: 'wb-step-label', style: { marginBottom: '1rem', textAlign: 'center' } }));

        // Content area
        container.appendChild(el('div', { id: 'wb-content' }));

        // Message area
        container.appendChild(el('div', { id: 'wb-msg', style: { marginTop: '0.5rem' } }));

        // Navigation buttons
        const nav = el('div', {
            style: {
                display: 'flex', justifyContent: 'space-between',
                marginTop: '1.5rem', paddingTop: '1rem',
                borderTop: '1px solid var(--border)',
            },
        });
        nav.appendChild(el('button', { id: 'wb-btn-back', onClick: prevStep }, 'Back'));
        nav.appendChild(el('button', { id: 'wb-btn-next', className: 'primary', onClick: nextStep }, 'Next'));
        container.appendChild(nav);

        overlay.appendChild(container);
        document.body.appendChild(overlay);
    }

    // ── Navigation ──

    function goToStep(step) {
        if (step < 0 || step >= TOTAL_STEPS) return;
        if (step > currentStep) {
            // Validate all steps up to current before jumping forward
            for (let i = currentStep; i < step; i++) {
                if (!validateStep(i)) return;
            }
        }
        currentStep = step;
        editingItem = null;
        renderStep();
    }

    function nextStep() {
        if (currentStep === TOTAL_STEPS - 1) {
            createWorld();
            return;
        }
        if (!validateStep(currentStep)) return;
        currentStep++;
        editingItem = null;
        renderStep();
    }

    function prevStep() {
        if (currentStep > 0) {
            currentStep--;
            editingItem = null;
            renderStep();
        }
    }

    function validateStep(step) {
        const msg = document.getElementById('wb-msg');
        msg.textContent = '';
        msg.className = '';

        switch (step) {
            case 0: {
                if (!worldData.id || !worldData.name) {
                    msg.textContent = 'World ID and Name are required.';
                    msg.className = 'text-danger mt-1';
                    return false;
                }
                return true;
            }
            default:
                return true;
        }
    }

    // ── Render current step ──

    function renderStep() {
        const content = document.getElementById('wb-content');
        const label = document.getElementById('wb-step-label');
        const msg = document.getElementById('wb-msg');
        const backBtn = document.getElementById('wb-btn-back');
        const nextBtn = document.getElementById('wb-btn-next');

        msg.textContent = '';
        msg.className = '';
        label.textContent = `Step ${currentStep + 1}: ${STEP_LABELS[currentStep]}`;

        // Update step indicators
        document.querySelectorAll('.wb-step-indicator').forEach(ind => {
            const s = parseInt(ind.dataset.step);
            if (s === currentStep) {
                ind.style.borderColor = 'var(--accent)';
                ind.style.background = 'var(--accent)';
                ind.style.color = '#fff';
            } else if (s < currentStep) {
                ind.style.borderColor = 'var(--success)';
                ind.style.background = 'transparent';
                ind.style.color = 'var(--success)';
            } else {
                ind.style.borderColor = 'var(--border)';
                ind.style.background = 'transparent';
                ind.style.color = 'var(--text-dim)';
            }
        });

        // Nav buttons
        backBtn.style.visibility = currentStep === 0 ? 'hidden' : 'visible';
        nextBtn.textContent = currentStep === TOTAL_STEPS - 1
            ? (editMode ? 'Save Changes' : 'Create World')
            : 'Next';

        // Update title
        const titleEl = document.getElementById('wb-title');
        if (titleEl) titleEl.textContent = editMode ? 'Edit World' : 'Create New World';

        content.innerHTML = '';

        const renderers = [
            renderWorldMeta, renderRegions, renderSettlements,
            renderLocations, renderNations, renderNpcs, renderReview,
        ];
        renderers[currentStep](content);
    }

    // ── Step 1: World Meta ──

    function renderWorldMeta(container) {
        container.innerHTML = `
            <div class="form-group mb-1">
                <label>Name</label>
                <input id="wb-name" value="${esc(worldData.name)}" placeholder="My World">
            </div>
            <div class="form-group mb-1">
                <label>ID (slug)</label>
                <input id="wb-id" value="${esc(worldData.id)}" placeholder="my_world" ${editMode ? 'disabled' : ''}>
            </div>
            <div class="form-group mb-1">
                <label>Description</label>
                <textarea id="wb-desc" rows="3" style="width:100%">${esc(worldData.description)}</textarea>
            </div>
        `;

        const nameInput = document.getElementById('wb-name');
        const idInput = document.getElementById('wb-id');

        let idManuallyEdited = worldData.id && worldData.id !== slugify(worldData.name);

        nameInput.addEventListener('input', () => {
            worldData.name = nameInput.value;
            if (!idManuallyEdited) {
                worldData.id = slugify(nameInput.value);
                idInput.value = worldData.id;
            }
        });
        idInput.addEventListener('input', () => {
            idManuallyEdited = true;
            worldData.id = slugify(idInput.value);
            idInput.value = worldData.id;
        });
        document.getElementById('wb-desc').addEventListener('input', (e) => {
            worldData.description = e.target.value;
        });
    }

    // ── Step 2: Regions ──

    function renderRegions(container) {
        const regionIds = Object.keys(worldData.regions);

        // Region cards
        const list = el('div', { id: 'wb-region-list' });
        regionIds.forEach(rid => {
            const r = worldData.regions[rid];
            const card = el('div', { className: 'card', style: { cursor: 'default' } });
            card.innerHTML = `
                <div class="flex justify-between items-center">
                    <div>
                        <strong>${esc(r.name)}</strong>
                        <span class="text-dim">(${esc(rid)})</span>
                        &mdash; ${esc(r.terrain)},
                        lat ${r.latitude}, lon ${r.longitude}, elev ${r.elevation}
                    </div>
                    <div>
                        <button class="small wb-edit-region" data-id="${esc(rid)}">Edit</button>
                        <button class="small danger wb-del-region" data-id="${esc(rid)}">Del</button>
                    </div>
                </div>
                ${r.connections.length
                    ? '<div class="text-dim" style="margin-top:0.3rem">Connections: ' +
                      r.connections.map(c => `${esc(c.target)} (${esc(c.direction)})`).join(', ') + '</div>'
                    : ''}
            `;
            list.appendChild(card);
        });
        container.appendChild(list);

        // Delegated clicks for edit/delete
        list.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.wb-edit-region');
            const delBtn = e.target.closest('.wb-del-region');
            if (editBtn) {
                editingItem = { type: 'region', id: editBtn.dataset.id };
                renderRegions(container);
            }
            if (delBtn) {
                const rid = delBtn.dataset.id;
                delete worldData.regions[rid];
                // Clean up connections referencing this region
                Object.values(worldData.regions).forEach(r => {
                    r.connections = r.connections.filter(c => c.target !== rid);
                });
                // Clean up settlements, locations, nations referencing this region
                Object.keys(worldData.locations).forEach(lid => {
                    if (worldData.locations[lid].region === rid) delete worldData.locations[lid];
                });
                Object.values(worldData.nations).forEach(n => {
                    n.regions = n.regions.filter(r => r !== rid);
                });
                editingItem = null;
                renderRegions(container);
            }
        });

        // Add/Edit form
        const existing = editingItem?.type === 'region' ? worldData.regions[editingItem.id] : null;
        const formTitle = existing ? 'Edit Region' : 'Add Region';

        container.appendChild(el('h3', { style: { marginTop: '1rem' } }, formTitle));

        const form = el('div', { className: 'panel', style: { marginTop: '0.5rem' } });
        form.innerHTML = `
            <div class="form-row">
                <div class="form-group grow">
                    <label>Name</label>
                    <input id="wb-rg-name" value="${esc(existing?.name || '')}">
                </div>
                <div class="form-group grow">
                    <label>ID</label>
                    <input id="wb-rg-id" value="${esc(existing ? editingItem.id : '')}" ${existing ? 'disabled' : ''}>
                </div>
                <div class="form-group">
                    <label>Terrain</label>
                    <select id="wb-rg-terrain">${selectOptions(TERRAINS, existing?.terrain || 'plains')}</select>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Latitude</label>
                    <input id="wb-rg-lat" type="number" step="0.1" value="${existing?.latitude ?? 45.0}">
                </div>
                <div class="form-group grow">
                    <label>Longitude</label>
                    <input id="wb-rg-lon" type="number" step="0.1" value="${existing?.longitude ?? 0.0}">
                </div>
                <div class="form-group grow">
                    <label>Elevation</label>
                    <input id="wb-rg-elev" type="number" value="${existing?.elevation ?? 100}">
                </div>
            </div>
            <div class="form-group mb-1">
                <label>Water Proximity: <span id="wb-rg-wp-val">${existing?.water_proximity ?? 0.0}</span></label>
                <input id="wb-rg-wp" type="range" min="0" max="1" step="0.05"
                       value="${existing?.water_proximity ?? 0.0}" style="width:100%">
            </div>
            ${regionIds.length >= 2 || (existing && regionIds.length >= 1)
                ? renderConnectionEditor(existing ? editingItem.id : null, existing?.connections || [])
                : ''}
            <div style="margin-top:0.75rem">
                <button class="primary" id="wb-rg-save">${existing ? 'Save Region' : 'Add Region'}</button>
                ${existing ? '<button id="wb-rg-cancel" style="margin-left:0.5rem">Cancel</button>' : ''}
            </div>
        `;
        container.appendChild(form);

        // Range slider live update
        const wpSlider = document.getElementById('wb-rg-wp');
        const wpVal = document.getElementById('wb-rg-wp-val');
        wpSlider.addEventListener('input', () => { wpVal.textContent = wpSlider.value; });

        // Auto-slug
        if (!existing) {
            const nameIn = document.getElementById('wb-rg-name');
            const idIn = document.getElementById('wb-rg-id');
            let manualId = false;
            nameIn.addEventListener('input', () => {
                if (!manualId) { idIn.value = slugify(nameIn.value); }
            });
            idIn.addEventListener('input', () => { manualId = true; idIn.value = slugify(idIn.value); });
        }

        // Save button
        document.getElementById('wb-rg-save').addEventListener('click', () => {
            const name = document.getElementById('wb-rg-name').value.trim();
            const id = existing ? editingItem.id : slugify(document.getElementById('wb-rg-id').value);
            if (!name || !id) {
                flashWbMsg('Region name and ID are required.', 'text-danger');
                return;
            }
            if (!existing && worldData.regions[id]) {
                flashWbMsg('Region ID already exists.', 'text-danger');
                return;
            }

            const connections = gatherConnections();

            worldData.regions[id] = {
                name,
                latitude: parseFloat(document.getElementById('wb-rg-lat').value) || 45.0,
                longitude: parseFloat(document.getElementById('wb-rg-lon').value) || 0.0,
                elevation: parseInt(document.getElementById('wb-rg-elev').value) || 100,
                terrain: document.getElementById('wb-rg-terrain').value,
                water_proximity: parseFloat(document.getElementById('wb-rg-wp').value) || 0.0,
                connections,
                settlements: existing ? (worldData.regions[id]?.settlements || []) : [],
            };

            editingItem = null;
            renderRegions(container);
        });

        // Cancel button
        const cancelBtn = document.getElementById('wb-rg-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                editingItem = null;
                renderRegions(container);
            });
        }
    }

    function renderConnectionEditor(currentRegionId, connections) {
        const otherRegions = Object.keys(worldData.regions).filter(r => r !== currentRegionId);
        if (otherRegions.length === 0) return '';

        let html = '<div class="mb-1"><label>Connections</label><div id="wb-conn-list">';
        connections.forEach((c, i) => {
            html += `
                <div class="form-row" data-conn="${i}">
                    <div class="form-group grow">
                        <select class="wb-conn-target">
                            <option value="">-- target --</option>
                            ${otherRegions.map(r =>
                                `<option value="${esc(r)}"${r === c.target ? ' selected' : ''}>${esc(worldData.regions[r]?.name || r)}</option>`
                            ).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <select class="wb-conn-dir">${selectOptions(DIRECTIONS, c.direction)}</select>
                    </div>
                    <button class="small danger wb-conn-del">X</button>
                </div>
            `;
        });
        html += '</div>';
        html += '<button class="small" id="wb-conn-add" style="margin-top:0.3rem">+ Connection</button></div>';
        return html;
    }

    function gatherConnections() {
        const list = document.getElementById('wb-conn-list');
        if (!list) return [];
        const connections = [];
        list.querySelectorAll('.form-row').forEach(row => {
            const target = row.querySelector('.wb-conn-target')?.value;
            const dir = row.querySelector('.wb-conn-dir')?.value;
            if (target && dir) connections.push({ target, direction: dir });
        });
        return connections;
    }

    // Delegated handler for connection add/delete (attached once per render via event delegation on container)
    document.addEventListener('click', (e) => {
        if (e.target.id === 'wb-conn-add') {
            const list = document.getElementById('wb-conn-list');
            if (!list) return;
            const currentRegionId = editingItem?.type === 'region' ? editingItem.id : null;
            const otherRegions = Object.keys(worldData.regions).filter(r => r !== currentRegionId);
            const row = el('div', { className: 'form-row' });
            row.innerHTML = `
                <div class="form-group grow">
                    <select class="wb-conn-target">
                        <option value="">-- target --</option>
                        ${otherRegions.map(r =>
                            `<option value="${esc(r)}">${esc(worldData.regions[r]?.name || r)}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <select class="wb-conn-dir">${selectOptions(DIRECTIONS, 'n')}</select>
                </div>
                <button class="small danger wb-conn-del">X</button>
            `;
            list.appendChild(row);
        }
        if (e.target.closest('.wb-conn-del')) {
            e.target.closest('.form-row').remove();
        }
    });

    // ── Step 3: Settlements ──

    function renderSettlements(container) {
        const regionIds = Object.keys(worldData.regions);

        if (regionIds.length === 0) {
            container.innerHTML = '<p class="text-dim">Add regions first (Step 2).</p>';
            return;
        }

        regionIds.forEach(rid => {
            const region = worldData.regions[rid];
            const header = el('h3', { style: { marginTop: '1rem' } },
                `${esc(region.name)} <span class="text-dim">(${esc(rid)})</span>`);
            container.appendChild(header);

            // Settlement list for this region
            (region.settlements || []).forEach((s, idx) => {
                const card = el('div', { className: 'card', style: { cursor: 'default' } });
                card.innerHTML = `
                    <div class="flex justify-between items-center">
                        <div>
                            <strong>${esc(s.name)}</strong>
                            <span class="text-dim">(${esc(s.id)})</span>
                            &mdash; ${esc(s.type)}, pop ${s.population},
                            prosp ${s.prosperity}, def ${s.defenses}
                        </div>
                        <div>
                            <button class="small wb-edit-sett" data-region="${esc(rid)}" data-idx="${idx}">Edit</button>
                            <button class="small danger wb-del-sett" data-region="${esc(rid)}" data-idx="${idx}">Del</button>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });

            // Show form if editing a settlement in this region, or show add button
            const isEditingHere = editingItem?.type === 'settlement' && editingItem.region === rid;
            if (isEditingHere) {
                container.appendChild(buildSettlementForm(rid, editingItem.idx));
            } else {
                const addBtn = el('button', {
                    className: 'small',
                    style: { marginTop: '0.3rem', marginBottom: '0.5rem' },
                    onClick: () => {
                        editingItem = { type: 'settlement', region: rid, idx: null };
                        renderSettlements(container);
                    },
                }, '+ Add Settlement');
                container.appendChild(addBtn);
            }
        });

        // Event delegation for edit/delete
        container.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.wb-edit-sett');
            const delBtn = e.target.closest('.wb-del-sett');
            if (editBtn) {
                editingItem = {
                    type: 'settlement',
                    region: editBtn.dataset.region,
                    idx: parseInt(editBtn.dataset.idx),
                };
                renderSettlements(container);
            }
            if (delBtn) {
                const rid = delBtn.dataset.region;
                const idx = parseInt(delBtn.dataset.idx);
                const settId = worldData.regions[rid].settlements[idx].id;
                worldData.regions[rid].settlements.splice(idx, 1);
                // Clean up locations referencing this settlement
                Object.keys(worldData.locations).forEach(lid => {
                    if (worldData.locations[lid].settlement === settId) {
                        worldData.locations[lid].settlement = '';
                    }
                });
                editingItem = null;
                renderSettlements(container);
            }
        }, { once: true });
    }

    function buildSettlementForm(regionId, idx) {
        const existing = idx != null ? worldData.regions[regionId].settlements[idx] : null;
        const form = el('div', { className: 'panel', style: { marginTop: '0.5rem' } });
        form.innerHTML = `
            <div class="form-row">
                <div class="form-group grow">
                    <label>Name</label>
                    <input id="wb-st-name" value="${esc(existing?.name || '')}">
                </div>
                <div class="form-group grow">
                    <label>ID</label>
                    <input id="wb-st-id" value="${esc(existing?.id || '')}" ${existing ? 'disabled' : ''}>
                </div>
                <div class="form-group">
                    <label>Type</label>
                    <select id="wb-st-type">${selectOptions(SETTLEMENT_TYPES, existing?.type || 'village')}</select>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Population</label>
                    <input id="wb-st-pop" type="number" value="${existing?.population ?? 200}">
                </div>
                <div class="form-group grow">
                    <label>Prosperity: <span id="wb-st-prosp-val">${existing?.prosperity ?? 50}</span></label>
                    <input id="wb-st-prosp" type="range" min="0" max="100" value="${existing?.prosperity ?? 50}">
                </div>
                <div class="form-group grow">
                    <label>Defenses: <span id="wb-st-def-val">${existing?.defenses ?? 20}</span></label>
                    <input id="wb-st-def" type="range" min="0" max="100" value="${existing?.defenses ?? 20}">
                </div>
            </div>
            <div style="margin-top:0.5rem">
                <button class="primary" id="wb-st-save">${existing ? 'Save Settlement' : 'Add Settlement'}</button>
                <button id="wb-st-cancel" style="margin-left:0.5rem">Cancel</button>
            </div>
        `;

        // Wire up after appending
        setTimeout(() => {
            const prospSlider = document.getElementById('wb-st-prosp');
            const prospVal = document.getElementById('wb-st-prosp-val');
            const defSlider = document.getElementById('wb-st-def');
            const defVal = document.getElementById('wb-st-def-val');
            if (prospSlider) prospSlider.addEventListener('input', () => { prospVal.textContent = prospSlider.value; });
            if (defSlider) defSlider.addEventListener('input', () => { defVal.textContent = defSlider.value; });

            // Auto-slug
            if (!existing) {
                const nameIn = document.getElementById('wb-st-name');
                const idIn = document.getElementById('wb-st-id');
                let manualId = false;
                nameIn.addEventListener('input', () => {
                    if (!manualId) idIn.value = slugify(nameIn.value);
                });
                idIn.addEventListener('input', () => { manualId = true; idIn.value = slugify(idIn.value); });
            }

            document.getElementById('wb-st-save').addEventListener('click', () => {
                const name = document.getElementById('wb-st-name').value.trim();
                const id = existing ? existing.id : slugify(document.getElementById('wb-st-id').value);
                if (!name || !id) {
                    flashWbMsg('Settlement name and ID are required.', 'text-danger');
                    return;
                }
                const sett = {
                    id, name,
                    type: document.getElementById('wb-st-type').value,
                    population: parseInt(document.getElementById('wb-st-pop').value) || 200,
                    prosperity: parseInt(document.getElementById('wb-st-prosp').value) || 50,
                    defenses: parseInt(document.getElementById('wb-st-def').value) || 20,
                };
                if (existing) {
                    worldData.regions[regionId].settlements[idx] = sett;
                } else {
                    worldData.regions[regionId].settlements.push(sett);
                }
                editingItem = null;
                const c = document.getElementById('wb-content');
                c.innerHTML = '';
                renderSettlements(c);
            });

            document.getElementById('wb-st-cancel').addEventListener('click', () => {
                editingItem = null;
                const c = document.getElementById('wb-content');
                c.innerHTML = '';
                renderSettlements(c);
            });
        }, 0);

        return form;
    }

    // ── Step 4: Locations ──

    function getAllSettlements() {
        const result = [];
        Object.entries(worldData.regions).forEach(([rid, r]) => {
            (r.settlements || []).forEach(s => {
                result.push({ ...s, region: rid });
            });
        });
        return result;
    }

    function renderLocations(container) {
        const locationIds = Object.keys(worldData.locations);

        // Auto-generate button
        const autoBtn = el('button', {
            className: 'primary',
            style: { marginBottom: '1rem' },
            onClick: () => {
                autoGenerateLocations();
                renderLocations(container);
            },
        }, 'Auto-generate Locations');
        container.appendChild(autoBtn);

        // Location cards
        const list = el('div', { id: 'wb-loc-list' });
        locationIds.forEach(lid => {
            const loc = worldData.locations[lid];
            const card = el('div', { className: 'card', style: { cursor: 'default' } });
            card.innerHTML = `
                <div class="flex justify-between items-center">
                    <div>
                        <strong>${esc(loc.name)}</strong>
                        <span class="text-dim">(${esc(lid)})</span>
                        &mdash; region: ${esc(loc.region)}${loc.settlement ? ', settlement: ' + esc(loc.settlement) : ''}
                    </div>
                    <div>
                        <button class="small wb-edit-loc" data-id="${esc(lid)}">Edit</button>
                        <button class="small danger wb-del-loc" data-id="${esc(lid)}">Del</button>
                    </div>
                </div>
                ${loc.description ? `<div class="text-dim" style="margin-top:0.2rem">${esc(loc.description)}</div>` : ''}
                ${loc.neighbors.length
                    ? '<div class="text-dim" style="margin-top:0.2rem">Neighbors: ' +
                      loc.neighbors.map(n => `${esc(n.target)} (${n.distance}m)`).join(', ') + '</div>'
                    : ''}
            `;
            list.appendChild(card);
        });
        container.appendChild(list);

        // Delegation
        list.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.wb-edit-loc');
            const delBtn = e.target.closest('.wb-del-loc');
            if (editBtn) {
                editingItem = { type: 'location', id: editBtn.dataset.id };
                container.innerHTML = '';
                renderLocations(container);
            }
            if (delBtn) {
                const lid = delBtn.dataset.id;
                delete worldData.locations[lid];
                // Clean up neighbor refs
                Object.values(worldData.locations).forEach(l => {
                    l.neighbors = l.neighbors.filter(n => n.target !== lid);
                });
                editingItem = null;
                container.innerHTML = '';
                renderLocations(container);
            }
        });

        // Add/Edit form
        const existing = editingItem?.type === 'location' ? worldData.locations[editingItem.id] : null;
        container.appendChild(el('h3', { style: { marginTop: '1rem' } }, existing ? 'Edit Location' : 'Add Location'));

        const regionIds = Object.keys(worldData.regions);
        const allSettlements = getAllSettlements();
        const otherLocations = Object.keys(worldData.locations).filter(l => l !== (editingItem?.id || ''));

        const form = el('div', { className: 'panel', style: { marginTop: '0.5rem' } });
        form.innerHTML = `
            <div class="form-row">
                <div class="form-group grow">
                    <label>Name</label>
                    <input id="wb-loc-name" value="${esc(existing?.name || '')}">
                </div>
                <div class="form-group grow">
                    <label>ID</label>
                    <input id="wb-loc-id" value="${esc(existing ? editingItem.id : '')}" ${existing ? 'disabled' : ''}>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Region</label>
                    <select id="wb-loc-region">
                        <option value="">-- select --</option>
                        ${regionIds.map(r =>
                            `<option value="${esc(r)}"${r === existing?.region ? ' selected' : ''}>${esc(worldData.regions[r].name)}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="form-group grow">
                    <label>Settlement (optional)</label>
                    <select id="wb-loc-sett">
                        <option value="">-- none --</option>
                        ${allSettlements.map(s =>
                            `<option value="${esc(s.id)}"${s.id === existing?.settlement ? ' selected' : ''}>${esc(s.name)} (${esc(s.region)})</option>`
                        ).join('')}
                    </select>
                </div>
            </div>
            <div class="form-group mb-1">
                <label>Description</label>
                <textarea id="wb-loc-desc" rows="2" style="width:100%">${esc(existing?.description || '')}</textarea>
            </div>
            <div class="mb-1">
                <label>Neighbors</label>
                <div id="wb-loc-neighbors">
                    ${(existing?.neighbors || []).map((n, i) => `
                        <div class="form-row" data-nbr="${i}">
                            <div class="form-group grow">
                                <select class="wb-nbr-target">
                                    <option value="">-- location --</option>
                                    ${otherLocations.map(l =>
                                        `<option value="${esc(l)}"${l === n.target ? ' selected' : ''}>${esc(worldData.locations[l]?.name || l)}</option>`
                                    ).join('')}
                                </select>
                            </div>
                            <div class="form-group">
                                <input class="wb-nbr-dist" type="number" placeholder="distance (m)" value="${n.distance}" style="width:100px">
                            </div>
                            <button class="small danger wb-nbr-del">X</button>
                        </div>
                    `).join('')}
                </div>
                <button class="small" id="wb-loc-nbr-add" style="margin-top:0.3rem">+ Neighbor</button>
            </div>
            <div style="margin-top:0.75rem">
                <button class="primary" id="wb-loc-save">${existing ? 'Save Location' : 'Add Location'}</button>
                ${existing ? '<button id="wb-loc-cancel" style="margin-left:0.5rem">Cancel</button>' : ''}
            </div>
        `;
        container.appendChild(form);

        // Auto-slug
        if (!existing) {
            const nameIn = document.getElementById('wb-loc-name');
            const idIn = document.getElementById('wb-loc-id');
            let manualId = false;
            nameIn.addEventListener('input', () => {
                if (!manualId) idIn.value = slugify(nameIn.value);
            });
            idIn.addEventListener('input', () => { manualId = true; idIn.value = slugify(idIn.value); });
        }

        // Neighbor add/delete
        document.getElementById('wb-loc-nbr-add').addEventListener('click', () => {
            const nbrList = document.getElementById('wb-loc-neighbors');
            const row = el('div', { className: 'form-row' });
            row.innerHTML = `
                <div class="form-group grow">
                    <select class="wb-nbr-target">
                        <option value="">-- location --</option>
                        ${otherLocations.map(l =>
                            `<option value="${esc(l)}">${esc(worldData.locations[l]?.name || l)}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <input class="wb-nbr-dist" type="number" placeholder="distance (m)" value="100" style="width:100px">
                </div>
                <button class="small danger wb-nbr-del">X</button>
            `;
            nbrList.appendChild(row);
        });

        document.getElementById('wb-loc-neighbors').addEventListener('click', (e) => {
            if (e.target.closest('.wb-nbr-del')) e.target.closest('.form-row').remove();
        });

        // Save
        document.getElementById('wb-loc-save').addEventListener('click', () => {
            const name = document.getElementById('wb-loc-name').value.trim();
            const id = existing ? editingItem.id : slugify(document.getElementById('wb-loc-id').value);
            const region = document.getElementById('wb-loc-region').value;
            if (!name || !id || !region) {
                flashWbMsg('Location name, ID, and region are required.', 'text-danger');
                return;
            }
            const neighbors = [];
            document.querySelectorAll('#wb-loc-neighbors .form-row').forEach(row => {
                const target = row.querySelector('.wb-nbr-target')?.value;
                const dist = parseInt(row.querySelector('.wb-nbr-dist')?.value) || 100;
                if (target) neighbors.push({ target, distance: dist });
            });

            worldData.locations[id] = {
                name,
                region,
                settlement: document.getElementById('wb-loc-sett').value || '',
                description: document.getElementById('wb-loc-desc').value.trim(),
                neighbors,
            };
            editingItem = null;
            container.innerHTML = '';
            renderLocations(container);
        });

        const cancelBtn = document.getElementById('wb-loc-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                editingItem = null;
                container.innerHTML = '';
                renderLocations(container);
            });
        }
    }

    function autoGenerateLocations() {
        const templates = ['home', 'tavern', 'smithy', 'market'];

        Object.entries(worldData.regions).forEach(([rid, region]) => {
            const settlements = region.settlements || [];

            if (settlements.length === 0) {
                // One location for bare region
                const locId = rid + '_clearing';
                if (!worldData.locations[locId]) {
                    worldData.locations[locId] = {
                        name: region.name + ' Clearing',
                        region: rid,
                        settlement: '',
                        description: 'An open area in ' + region.name + '.',
                        neighbors: [],
                    };
                }
            } else {
                settlements.forEach(sett => {
                    const settLocIds = [];
                    templates.forEach(tmpl => {
                        const locId = sett.id + '_' + tmpl;
                        if (!worldData.locations[locId]) {
                            const names = {
                                home: 'Town Square',
                                tavern: 'Tavern',
                                smithy: 'Smithy',
                                market: 'Market',
                            };
                            worldData.locations[locId] = {
                                name: sett.name + ' ' + names[tmpl],
                                region: rid,
                                settlement: sett.id,
                                description: 'The ' + names[tmpl].toLowerCase() + ' of ' + sett.name + '.',
                                neighbors: [],
                            };
                        }
                        settLocIds.push(locId);
                    });
                    // Connect locations within a settlement to the town square
                    const hubId = settLocIds[0];
                    settLocIds.slice(1).forEach(lid => {
                        const hub = worldData.locations[hubId];
                        const loc = worldData.locations[lid];
                        if (!hub.neighbors.find(n => n.target === lid)) {
                            hub.neighbors.push({ target: lid, distance: 50 });
                        }
                        if (!loc.neighbors.find(n => n.target === hubId)) {
                            loc.neighbors.push({ target: hubId, distance: 50 });
                        }
                    });
                });
            }
        });
    }

    // ── Step 5: Nations ──

    function renderNations(container) {
        const nationIds = Object.keys(worldData.nations);

        // Nation cards
        const list = el('div', { id: 'wb-nation-list' });
        nationIds.forEach(nid => {
            const n = worldData.nations[nid];
            const card = el('div', { className: 'card', style: { cursor: 'default' } });
            card.innerHTML = `
                <div class="flex justify-between items-center">
                    <div>
                        <strong>${esc(n.name)}</strong>
                        <span class="text-dim">(${esc(nid)})</span>
                        &mdash; W:${n.wealth} M:${n.military} S:${n.stability}
                        ${n.leader ? `, Leader: ${esc(n.leader.name)} (${esc(n.leader.trait)})` : ''}
                    </div>
                    <div>
                        <button class="small wb-edit-nation" data-id="${esc(nid)}">Edit</button>
                        <button class="small danger wb-del-nation" data-id="${esc(nid)}">Del</button>
                    </div>
                </div>
                <div class="text-dim" style="margin-top:0.2rem">Regions: ${n.regions.map(r => esc(worldData.regions[r]?.name || r)).join(', ') || 'none'}</div>
            `;
            list.appendChild(card);
        });
        container.appendChild(list);

        list.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.wb-edit-nation');
            const delBtn = e.target.closest('.wb-del-nation');
            if (editBtn) {
                editingItem = { type: 'nation', id: editBtn.dataset.id };
                container.innerHTML = '';
                renderNations(container);
            }
            if (delBtn) {
                delete worldData.nations[delBtn.dataset.id];
                editingItem = null;
                container.innerHTML = '';
                renderNations(container);
            }
        });

        // Add/Edit form
        const existing = editingItem?.type === 'nation' ? worldData.nations[editingItem.id] : null;
        container.appendChild(el('h3', { style: { marginTop: '1rem' } }, existing ? 'Edit Nation' : 'Add Nation'));

        const regionIds = Object.keys(worldData.regions);
        const form = el('div', { className: 'panel', style: { marginTop: '0.5rem' } });
        form.innerHTML = `
            <div class="form-row">
                <div class="form-group grow">
                    <label>Name</label>
                    <input id="wb-nat-name" value="${esc(existing?.name || '')}">
                </div>
                <div class="form-group grow">
                    <label>ID</label>
                    <input id="wb-nat-id" value="${esc(existing ? editingItem.id : '')}" ${existing ? 'disabled' : ''}>
                </div>
            </div>
            <div class="form-group mb-1">
                <label>Regions</label>
                <div id="wb-nat-regions" style="display:flex;flex-wrap:wrap;gap:0.5rem">
                    ${regionIds.map(rid => `
                        <label style="display:flex;align-items:center;gap:0.3rem;cursor:pointer;color:var(--text)">
                            <input type="checkbox" class="wb-nat-rgn-cb" value="${esc(rid)}"
                                   ${existing?.regions.includes(rid) ? 'checked' : ''}>
                            ${esc(worldData.regions[rid].name)}
                        </label>
                    `).join('')}
                </div>
            </div>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Wealth: <span id="wb-nat-w-val">${existing?.wealth ?? 50}</span></label>
                    <input id="wb-nat-wealth" type="range" min="0" max="100" value="${existing?.wealth ?? 50}">
                </div>
                <div class="form-group grow">
                    <label>Military: <span id="wb-nat-m-val">${existing?.military ?? 50}</span></label>
                    <input id="wb-nat-military" type="range" min="0" max="100" value="${existing?.military ?? 50}">
                </div>
                <div class="form-group grow">
                    <label>Stability: <span id="wb-nat-s-val">${existing?.stability ?? 70}</span></label>
                    <input id="wb-nat-stability" type="range" min="0" max="100" value="${existing?.stability ?? 70}">
                </div>
            </div>
            <h3 style="margin-top:0.75rem">Leader</h3>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Name</label>
                    <input id="wb-nat-leader-name" value="${esc(existing?.leader?.name || '')}">
                </div>
                <div class="form-group">
                    <label>Age</label>
                    <input id="wb-nat-leader-age" type="number" value="${existing?.leader?.age ?? 45}" style="width:70px">
                </div>
                <div class="form-group">
                    <label>Trait</label>
                    <select id="wb-nat-leader-trait">${selectOptions(LEADER_TRAITS, existing?.leader?.trait || 'merchant')}</select>
                </div>
            </div>
            <div style="margin-top:0.75rem">
                <button class="primary" id="wb-nat-save">${existing ? 'Save Nation' : 'Add Nation'}</button>
                ${existing ? '<button id="wb-nat-cancel" style="margin-left:0.5rem">Cancel</button>' : ''}
            </div>
        `;
        container.appendChild(form);

        // Slider live updates
        ['wealth', 'military', 'stability'].forEach(f => {
            const slider = document.getElementById('wb-nat-' + f);
            const valSpan = document.getElementById('wb-nat-' + f[0] + '-val');
            if (slider && valSpan) slider.addEventListener('input', () => { valSpan.textContent = slider.value; });
        });

        // Auto-slug
        if (!existing) {
            const nameIn = document.getElementById('wb-nat-name');
            const idIn = document.getElementById('wb-nat-id');
            let manualId = false;
            nameIn.addEventListener('input', () => {
                if (!manualId) idIn.value = slugify(nameIn.value);
            });
            idIn.addEventListener('input', () => { manualId = true; idIn.value = slugify(idIn.value); });
        }

        // Save
        document.getElementById('wb-nat-save').addEventListener('click', () => {
            const name = document.getElementById('wb-nat-name').value.trim();
            const id = existing ? editingItem.id : slugify(document.getElementById('wb-nat-id').value);
            if (!name || !id) {
                flashWbMsg('Nation name and ID are required.', 'text-danger');
                return;
            }
            const regions = [];
            document.querySelectorAll('.wb-nat-rgn-cb:checked').forEach(cb => regions.push(cb.value));

            const leaderName = document.getElementById('wb-nat-leader-name').value.trim();
            const leader = leaderName ? {
                name: leaderName,
                age: parseInt(document.getElementById('wb-nat-leader-age').value) || 45,
                trait: document.getElementById('wb-nat-leader-trait').value,
            } : null;

            worldData.nations[id] = {
                name, regions,
                wealth: parseInt(document.getElementById('wb-nat-wealth').value) || 50,
                military: parseInt(document.getElementById('wb-nat-military').value) || 50,
                stability: parseInt(document.getElementById('wb-nat-stability').value) || 70,
                leader,
            };
            editingItem = null;
            container.innerHTML = '';
            renderNations(container);
        });

        const cancelBtn = document.getElementById('wb-nat-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                editingItem = null;
                container.innerHTML = '';
                renderNations(container);
            });
        }
    }

    // ── Step 6: NPCs ──

    function renderNpcs(container) {
        const npcIds = Object.keys(worldData.npcs);

        // NPC cards
        const list = el('div', { id: 'wb-npc-list' });
        npcIds.forEach(nid => {
            const npc = worldData.npcs[nid];
            const card = el('div', { className: 'card', style: { cursor: 'default' } });
            card.innerHTML = `
                <div class="flex justify-between items-center">
                    <div>
                        <strong>${esc(npc.name)}</strong>
                        <span class="text-dim">(${esc(nid)})</span>
                        &mdash; ${esc(npc.race)} ${esc(npc.class)}, ${esc(npc.role)},
                        HP:${npc.hp} AC:${npc.ac}, AI:${esc(npc.ai)}
                    </div>
                    <div>
                        <button class="small wb-edit-npc" data-id="${esc(nid)}">Edit</button>
                        <button class="small danger wb-del-npc" data-id="${esc(nid)}">Del</button>
                    </div>
                </div>
            `;
            list.appendChild(card);
        });
        container.appendChild(list);

        list.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.wb-edit-npc');
            const delBtn = e.target.closest('.wb-del-npc');
            if (editBtn) {
                editingItem = { type: 'npc', id: editBtn.dataset.id };
                container.innerHTML = '';
                renderNpcs(container);
            }
            if (delBtn) {
                delete worldData.npcs[delBtn.dataset.id];
                editingItem = null;
                container.innerHTML = '';
                renderNpcs(container);
            }
        });

        // Add/Edit form
        const existing = editingItem?.type === 'npc' ? worldData.npcs[editingItem.id] : null;
        container.appendChild(el('h3', { style: { marginTop: '1rem' } }, existing ? 'Edit NPC' : 'Add NPC'));

        const allSettlements = getAllSettlements();
        const allLocations = Object.entries(worldData.locations);

        const form = el('div', { className: 'panel', style: { marginTop: '0.5rem' } });
        const scores = existing?.ability_scores || {};
        const attacks = existing?.attacks || [];

        form.innerHTML = `
            <h3>Basic</h3>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Name</label>
                    <input id="wb-npc-name" value="${esc(existing?.name || '')}">
                </div>
                <div class="form-group grow">
                    <label>ID</label>
                    <input id="wb-npc-id" value="${esc(existing ? editingItem.id : '')}" ${existing ? 'disabled' : ''}>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Role</label>
                    <input id="wb-npc-role" value="${esc(existing?.role || '')}" placeholder="blacksmith">
                </div>
                <div class="form-group grow">
                    <label>Personality</label>
                    <textarea id="wb-npc-personality" rows="2" style="width:100%">${esc(existing?.personality || '')}</textarea>
                </div>
            </div>

            <h3 style="margin-top:0.75rem">Binding</h3>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Settlement</label>
                    <select id="wb-npc-sett">
                        <option value="">-- none --</option>
                        ${allSettlements.map(s =>
                            `<option value="${esc(s.id)}"${s.id === existing?.settlement_id ? ' selected' : ''}>${esc(s.name)} (${esc(s.region)})</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="form-group grow">
                    <label>Start Location</label>
                    <select id="wb-npc-loc">
                        <option value="">-- select --</option>
                        ${allLocations.map(([lid, loc]) =>
                            `<option value="${esc(lid)}"${lid === existing?.start_location ? ' selected' : ''}>${esc(loc.name)} (${esc(lid)})</option>`
                        ).join('')}
                    </select>
                </div>
            </div>

            <h3 style="margin-top:0.75rem">Race & Class</h3>
            <div class="form-row">
                <div class="form-group grow">
                    <label>Race</label>
                    <select id="wb-npc-race">${selectOptions(RACES, existing?.race || 'human')}</select>
                </div>
                <div class="form-group grow">
                    <label>Class</label>
                    <select id="wb-npc-class">${selectOptions(CLASSES, existing?.class || 'commoner')}</select>
                </div>
            </div>

            <h3 style="margin-top:0.75rem">Stats</h3>
            <div class="form-row">
                <div class="form-group">
                    <label>HP</label>
                    <input id="wb-npc-hp" type="number" value="${existing?.hp ?? 18}" style="width:60px">
                </div>
                <div class="form-group">
                    <label>AC</label>
                    <input id="wb-npc-ac" type="number" value="${existing?.ac ?? 12}" style="width:60px">
                </div>
                <div class="form-group">
                    <label>Speed</label>
                    <input id="wb-npc-speed" type="number" value="${existing?.speed ?? 30}" style="width:60px">
                </div>
            </div>
            <div class="form-row">
                ${ABILITIES.map(ab => `
                    <div class="form-group">
                        <label>${ab.toUpperCase()}</label>
                        <input class="wb-npc-ability" data-ability="${ab}" type="number"
                               value="${scores[ab] ?? 10}" style="width:50px">
                    </div>
                `).join('')}
            </div>

            <h3 style="margin-top:0.75rem">AI</h3>
            <div class="form-row">
                <label style="display:flex;align-items:center;gap:0.3rem;color:var(--text);cursor:pointer">
                    <input type="radio" name="wb-npc-ai" value="rule_based"
                           ${(!existing || existing.ai === 'rule_based') ? 'checked' : ''}> rule_based
                </label>
                <label style="display:flex;align-items:center;gap:0.3rem;color:var(--text);cursor:pointer">
                    <input type="radio" name="wb-npc-ai" value="llm"
                           ${existing?.ai === 'llm' ? 'checked' : ''}> llm
                </label>
            </div>

            <h3 style="margin-top:0.75rem">Attacks</h3>
            <div id="wb-npc-attacks"></div>
            <button class="small" id="wb-npc-atk-add" style="margin-top:0.3rem">+ Attack</button>

            <div style="margin-top:1rem">
                <button class="primary" id="wb-npc-save">${existing ? 'Save NPC' : 'Add NPC'}</button>
                ${existing ? '<button id="wb-npc-cancel" style="margin-left:0.5rem">Cancel</button>' : ''}
            </div>
        `;
        container.appendChild(form);

        // Settlement -> Location filtering
        const settSelect = document.getElementById('wb-npc-sett');
        const locSelect = document.getElementById('wb-npc-loc');
        settSelect.addEventListener('change', () => {
            const settId = settSelect.value;
            locSelect.innerHTML = '<option value="">-- select --</option>';
            allLocations.forEach(([lid, loc]) => {
                if (!settId || loc.settlement === settId) {
                    locSelect.innerHTML += `<option value="${esc(lid)}">${esc(loc.name)} (${esc(lid)})</option>`;
                }
            });
        });

        // Auto-slug
        if (!existing) {
            const nameIn = document.getElementById('wb-npc-name');
            const idIn = document.getElementById('wb-npc-id');
            let manualId = false;
            nameIn.addEventListener('input', () => {
                if (!manualId) idIn.value = slugify(nameIn.value);
            });
            idIn.addEventListener('input', () => { manualId = true; idIn.value = slugify(idIn.value); });
        }

        // Attacks
        const atkContainer = document.getElementById('wb-npc-attacks');
        attacks.forEach(atk => addAttackRow(atkContainer, atk));

        document.getElementById('wb-npc-atk-add').addEventListener('click', () => {
            addAttackRow(atkContainer, null);
        });

        // Save
        document.getElementById('wb-npc-save').addEventListener('click', () => {
            const name = document.getElementById('wb-npc-name').value.trim();
            const id = existing ? editingItem.id : slugify(document.getElementById('wb-npc-id').value);
            if (!name || !id) {
                flashWbMsg('NPC name and ID are required.', 'text-danger');
                return;
            }

            const ability_scores = {};
            document.querySelectorAll('.wb-npc-ability').forEach(inp => {
                ability_scores[inp.dataset.ability] = parseInt(inp.value) || 10;
            });

            const gatheredAttacks = gatherAttacks();

            worldData.npcs[id] = {
                name,
                start_location: document.getElementById('wb-npc-loc').value || '',
                settlement_id: document.getElementById('wb-npc-sett').value || '',
                role: document.getElementById('wb-npc-role').value.trim(),
                personality: document.getElementById('wb-npc-personality').value.trim(),
                race: document.getElementById('wb-npc-race').value,
                class: document.getElementById('wb-npc-class').value,
                hp: parseInt(document.getElementById('wb-npc-hp').value) || 18,
                ac: parseInt(document.getElementById('wb-npc-ac').value) || 12,
                speed: parseInt(document.getElementById('wb-npc-speed').value) || 30,
                ability_scores,
                ai: document.querySelector('input[name="wb-npc-ai"]:checked')?.value || 'rule_based',
                attacks: gatheredAttacks,
            };

            editingItem = null;
            container.innerHTML = '';
            renderNpcs(container);
        });

        const cancelBtn = document.getElementById('wb-npc-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                editingItem = null;
                container.innerHTML = '';
                renderNpcs(container);
            });
        }
    }

    function addAttackRow(atkContainer, atk) {
        const idx = atkContainer.children.length;
        const row = el('div', {
            className: 'panel',
            style: { marginBottom: '0.5rem', padding: '0.5rem' },
            'data-atk-idx': String(idx),
        });
        row.innerHTML = `
            <div class="form-row">
                <div class="form-group grow">
                    <label>Name</label>
                    <input class="wb-atk-name" value="${esc(atk?.name || '')}">
                </div>
                <div class="form-group">
                    <label>Ability</label>
                    <select class="wb-atk-ability">${selectOptions(ABILITIES, atk?.ability || 'str')}</select>
                </div>
                <div class="form-group">
                    <button class="small danger wb-atk-del" style="margin-top:1.2rem">Remove</button>
                </div>
            </div>
            <div class="wb-atk-damages"></div>
            <button class="small wb-atk-dmg-add" style="margin-top:0.3rem">+ Damage</button>
        `;
        atkContainer.appendChild(row);

        const dmgContainer = row.querySelector('.wb-atk-damages');
        (atk?.damage || []).forEach(d => addDamageRow(dmgContainer, d));

        row.querySelector('.wb-atk-dmg-add').addEventListener('click', () => {
            addDamageRow(dmgContainer, null);
        });

        row.querySelector('.wb-atk-del').addEventListener('click', () => {
            row.remove();
        });
    }

    function addDamageRow(dmgContainer, d) {
        const row = el('div', { className: 'form-row' });
        row.innerHTML = `
            <div class="form-group grow">
                <label>Dice</label>
                <input class="wb-dmg-dice" value="${esc(d?.dice || '1d6')}" placeholder="1d6" style="width:70px">
            </div>
            <div class="form-group grow">
                <label>Type</label>
                <select class="wb-dmg-type">${selectOptions(DAMAGE_TYPES, d?.type || 'bludgeoning')}</select>
            </div>
            <button class="small danger wb-dmg-del" style="margin-top:1.2rem">X</button>
        `;
        dmgContainer.appendChild(row);

        row.querySelector('.wb-dmg-del').addEventListener('click', () => {
            row.remove();
        });
    }

    function gatherAttacks() {
        const attacks = [];
        document.querySelectorAll('#wb-npc-attacks > div').forEach(row => {
            const name = row.querySelector('.wb-atk-name')?.value.trim();
            const ability = row.querySelector('.wb-atk-ability')?.value;
            if (!name) return;

            const damage = [];
            row.querySelectorAll('.wb-atk-damages .form-row').forEach(dr => {
                const dice = dr.querySelector('.wb-dmg-dice')?.value.trim();
                const type = dr.querySelector('.wb-dmg-type')?.value;
                if (dice) damage.push({ dice, type });
            });

            attacks.push({ name, ability, damage });
        });
        return attacks;
    }

    // ── Step 7: Review ──

    function renderReview(container) {
        const regionCount = Object.keys(worldData.regions).length;
        const settCount = Object.values(worldData.regions).reduce((sum, r) => sum + (r.settlements?.length || 0), 0);
        const locCount = Object.keys(worldData.locations).length;
        const nationCount = Object.keys(worldData.nations).length;
        const npcCount = Object.keys(worldData.npcs).length;

        container.innerHTML = `
            <div class="stat-grid mb-1">
                <span class="stat-label">World ID</span><span class="stat-value">${esc(worldData.id)}</span>
                <span class="stat-label">Name</span><span class="stat-value">${esc(worldData.name)}</span>
                <span class="stat-label">Regions</span><span class="stat-value">${regionCount}</span>
                <span class="stat-label">Settlements</span><span class="stat-value">${settCount}</span>
                <span class="stat-label">Locations</span><span class="stat-value">${locCount}</span>
                <span class="stat-label">Nations</span><span class="stat-value">${nationCount}</span>
                <span class="stat-label">NPCs</span><span class="stat-value">${npcCount}</span>
            </div>
            ${worldData.description ? `<p class="text-dim mb-1">${esc(worldData.description)}</p>` : ''}
            <details style="margin-top:1rem">
                <summary style="cursor:pointer;color:var(--accent);margin-bottom:0.5rem">JSON Preview</summary>
                <pre id="wb-json-preview" style="background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:0.75rem;overflow-x:auto;font-size:0.8rem;max-height:400px;overflow-y:auto"></pre>
            </details>
        `;

        const preview = document.getElementById('wb-json-preview');
        preview.textContent = JSON.stringify(buildPayload(), null, 2);
    }

    // ── Build API payload ──

    function buildPayload() {
        return {
            id: worldData.id,
            name: worldData.name,
            description: worldData.description,
            regions: { ...worldData.regions },
            locations: { ...worldData.locations },
            nations: { ...worldData.nations },
            npcs: { ...worldData.npcs },
        };
    }

    // ── Create world via API ──

    async function createWorld() {
        const msg = document.getElementById('wb-msg');
        const btn = document.getElementById('wb-btn-next');
        msg.textContent = '';
        msg.className = '';
        btn.disabled = true;
        btn.textContent = editMode ? 'Saving...' : 'Creating...';

        try {
            const payload = buildPayload();
            let result;
            if (editMode) {
                result = await API.master.updateWorld(worldData.id, payload);
            } else {
                result = await API.master.createWorld(payload);
            }
            msg.textContent = editMode ? 'World updated!' : 'World created successfully!';
            msg.className = 'text-success mt-1';
            btn.textContent = 'Done';

            if (typeof onCreated === 'function') {
                onCreated(result);
            }

            // Auto-close after a short delay
            setTimeout(() => { close(); }, 1500);
        } catch (err) {
            msg.textContent = 'Error: ' + err.message;
            msg.className = 'text-danger mt-1';
            btn.disabled = false;
            btn.textContent = editMode ? 'Save Changes' : 'Create World';
        }
    }

    // ── Flash message ──

    function flashWbMsg(text, cls) {
        const msg = document.getElementById('wb-msg');
        if (!msg) return;
        msg.textContent = text;
        msg.className = cls + ' mt-1';
        setTimeout(() => { msg.textContent = ''; msg.className = ''; }, 4000);
    }

    // ── Public API ──

    function open() {
        resetWizard();
        if (!overlay) createOverlay();
        overlay.style.display = 'flex';
        renderStep();
    }

    function openForEdit(templateData) {
        resetWizard();
        editMode = true;
        worldData = templateToWorldData(templateData);
        if (!overlay) createOverlay();
        overlay.style.display = 'flex';
        renderStep();
    }

    function close() {
        if (overlay) overlay.style.display = 'none';
    }

    return {
        open,
        openForEdit,
        close,
        get onCreated() { return onCreated; },
        set onCreated(fn) { onCreated = fn; },
    };
})();
