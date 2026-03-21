/**
 * D&D Simulator API client — thin fetch wrapper over REST endpoints.
 */
const API = (() => {
    const BASE = '/api';

    async function request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body !== null) opts.body = JSON.stringify(body);
        const res = await fetch(BASE + path, opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || JSON.stringify(err));
        }
        return res.json();
    }

    const get = (path) => request('GET', path);
    const post = (path, body) => request('POST', path, body);
    const patch = (path, body) => request('PATCH', path, body);
    const put = (path, body) => request('PUT', path, body);
    const del = (path) => request('DELETE', path);

    // ── Master ──

    const master = {
        listWorlds: () => get('/master/worlds'),

        createWorld: (data) => post('/master/worlds', data),

        updateWorld: (worldId, data) => put(`/master/worlds/${worldId}`, data),

        getWorldTemplate: (worldId) => get(`/master/worlds/${worldId}`),

        listSessions: () => get('/master/sessions'),

        createSession: (worldName, lang = 'ru') =>
            post('/master/sessions', { world_name: worldName, lang }),

        getSession: (sid) => get(`/master/sessions/${sid}`),

        deleteSession: (sid) => del(`/master/sessions/${sid}`),

        // NPCs
        listNpcs: (sid) => get(`/master/sessions/${sid}/npcs`),
        getNpc: (sid, npcId) => get(`/master/sessions/${sid}/npcs/${npcId}`),
        spawnNpc: (sid, data) => post(`/master/sessions/${sid}/npcs`, data),
        patchNpc: (sid, npcId, data) => patch(`/master/sessions/${sid}/npcs/${npcId}`, data),
        deleteNpc: (sid, npcId) => del(`/master/sessions/${sid}/npcs/${npcId}`),
        setBrain: (sid, npcId, type, model = null) =>
            put(`/master/sessions/${sid}/npcs/${npcId}/brain`, { type, model }),

        // Nations & Settlements
        patchNation: (sid, nationId, data) =>
            patch(`/master/sessions/${sid}/nations/${nationId}`, data),
        patchSettlement: (sid, settlementId, data) =>
            patch(`/master/sessions/${sid}/settlements/${settlementId}`, data),

        // Time
        advanceTime: (sid, hours) =>
            post(`/master/sessions/${sid}/time/advance`, { hours }),

        // Language
        setLang: (sid, lang) =>
            put(`/master/sessions/${sid}/lang`, { lang }),

        // Saves
        listSaves: (sid) => get(`/master/sessions/${sid}/saves`),
        save: (sid, name = null) =>
            post(`/master/sessions/${sid}/save` + (name ? `?name=${encodeURIComponent(name)}` : '')),
        load: (sid, saveName) =>
            post(`/master/sessions/${sid}/saves/${saveName}/load`),
    };

    // ── Player ──

    const player = {
        createCharacter: (sid, data) =>
            post(`/player/sessions/${sid}/character`, data),

        getStatus: (sid) => get(`/player/sessions/${sid}/status`),

        action: (sid, actionText) =>
            post(`/player/sessions/${sid}/action`, { action: actionText }),

        getPerception: (sid) => get(`/player/sessions/${sid}/perception`),

        getEvents: (sid) => get(`/player/sessions/${sid}/events`),

        getCombat: (sid) => get(`/player/sessions/${sid}/combat`),

        getMap: (sid) => get(`/player/sessions/${sid}/map`),
    };

    return { master, player };
})();
