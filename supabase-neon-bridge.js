/**
 * 24Seven Neon-Supabase Bridge
 * Replaces direct Supabase client calls with ultra-fast queries to Neon Postgres over Vercel/Render API.
 */
(function() {
    console.log("⚡ 24Seven Neon-Postgres Bridge Active (Replacing Supabase 402 with Neon Cloud)");

    function getApiEndpoint() {
        const loc = window.location;
        if (loc.hostname.includes('24seven-ai.com') || loc.hostname.includes('onrender.com') || loc.hostname.includes('vercel.app')) {
            return `${loc.protocol}//${loc.hostname}${loc.port ? ':' + loc.port : ''}/api/db`;
        }
        if (loc.protocol === 'file:') return 'http://localhost:3000/api/db';
        return `${loc.origin}/api/db`;
    }

    class NeonQueryBuilder {
        constructor(table) {
            this.tableName = table;
            this.action = 'select';
            this.selectCols = '*';
            this.filters = [];
            this.orderConfig = null;
            this.limitVal = null;
            this.insertData = null;
            this.updateData = null;
            this.isSingle = false;
            this.isMaybeSingle = false;
        }

        select(cols = '*', opts = {}) {
            this.action = 'select';
            this.selectCols = cols;
            if (opts && (opts.count || opts.head)) {
                this.isHead = true;
                this.limitVal = 1;
            }
            return this;
        }

        insert(data) {
            this.action = 'insert';
            this.insertData = data;
            return this;
        }

        update(data) {
            this.action = 'update';
            this.updateData = data;
            return this;
        }

        delete() {
            this.action = 'delete';
            return this;
        }

        upsert(data) {
            this.action = 'insert';
            this.insertData = data;
            return this;
        }

        eq(col, val) {
            this.filters.push({ op: 'eq', col, val });
            return this;
        }

        neq(col, val) {
            this.filters.push({ op: 'neq', col, val });
            return this;
        }

        gt(col, val) {
            this.filters.push({ op: 'gt', col, val });
            return this;
        }

        gte(col, val) {
            this.filters.push({ op: 'gte', col, val });
            return this;
        }

        lt(col, val) {
            this.filters.push({ op: 'lt', col, val });
            return this;
        }

        lte(col, val) {
            this.filters.push({ op: 'lte', col, val });
            return this;
        }

        like(col, val) {
            this.filters.push({ op: 'like', col, val });
            return this;
        }

        ilike(col, val) {
            this.filters.push({ op: 'ilike', col, val });
            return this;
        }

        in(col, val) {
            this.filters.push({ op: 'in', col, val: Array.isArray(val) ? val : [val] });
            return this;
        }

        is(col, val) {
            this.filters.push({ op: 'is', col, val });
            return this;
        }

        not(col, op, val) {
            if (op === 'in') {
                this.filters.push({ op: 'neq', col, val });
            } else {
                this.filters.push({ op: 'neq', col, val });
            }
            return this;
        }

        or(val) {
            this.filters.push({ op: 'or', val });
            return this;
        }

        order(col, opts = { ascending: true }) {
            this.orderConfig = { col, ascending: opts.ascending !== false };
            return this;
        }

        limit(n) {
            this.limitVal = n;
            return this;
        }

        single() {
            this.isSingle = true;
            this.limitVal = 1;
            return this.execute();
        }

        maybeSingle() {
            this.isMaybeSingle = true;
            this.limitVal = 1;
            return this.execute();
        }

        async execute() {
            const endpoint = getApiEndpoint();
            const payload = {
                action: this.action,
                table: this.tableName,
                select: this.selectCols,
                filters: this.filters,
                order: this.orderConfig,
                limit: this.limitVal
            };

            if (this.action === 'insert') {
                payload.data = this.insertData;
            } else if (this.action === 'update') {
                payload.data = this.updateData;
                payload.eq = {};
                this.filters.filter(f => f.op === 'eq').forEach(f => {
                    payload.eq[f.col] = f.val;
                });
            } else if (this.action === 'delete') {
                payload.eq = {};
                this.filters.filter(f => f.op === 'eq').forEach(f => {
                    payload.eq[f.col] = f.val;
                });
            }

            if (this.isHead) {
                payload.select = 'id';
                payload.limit = 1;
                payload.order = { col: 'id', ascending: false };
            }

            try {
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!resp.ok) {
                    return { data: null, error: { message: `HTTP ${resp.status}`, status: resp.status } };
                }

                const json = await resp.json();
                let data = json.data;

                if (this.isSingle) {
                    if (Array.isArray(data)) {
                        data = data.length > 0 ? data[0] : null;
                    }
                    if (!data) {
                        return { data: null, error: { message: 'Row not found' } };
                    }
                    return { data, error: null };
                }

                if (this.isMaybeSingle) {
                    if (Array.isArray(data)) {
                        data = data.length > 0 ? data[0] : null;
                    }
                    return { data, error: null };
                }

                let countVal = json.count;
                if (this.isHead) {
                    const firstRow = (Array.isArray(data) && data.length > 0) ? data[0] : null;
                    countVal = firstRow ? (Number(firstRow.id) || 0) : 0;
                }

                return { data: data || [], error: null, count: countVal };

            } catch (err) {
                console.error(`Neon query error on ${this.tableName}:`, err);
                return { data: null, error: { message: err.message } };
            }
        }

        // Make it thenable for async/await
        then(onFulfilled, onRejected) {
            return this.execute().then(onFulfilled, onRejected);
        }
    }

    class NeonClient {
        constructor() {}

        from(table) {
            return new NeonQueryBuilder(table);
        }

        channel() {
            return {
                on: function() { return this; },
                subscribe: function(cb) {
                    if (typeof cb === 'function') cb('SUBSCRIBED');
                    return this;
                },
                unsubscribe: function() { return true; }
            };
        }

        removeChannel() { return true; }
        getChannels() { return []; }
    }

    // Override or Polyfill supabase.createClient
    const neonClientInstance = new NeonClient();

    window.createNeonSupabaseClient = function() {
        return neonClientInstance;
    };

    // Replace global supabase.createClient
    if (typeof window.supabase === 'undefined') {
        window.supabase = {
            createClient: function() { return neonClientInstance; }
        };
    } else {
        const origCreateClient = window.supabase.createClient;
        window.supabase.createClient = function(url, key) {
            // Always return our NeonClient to bypass Supabase 402 locks completely!
            return new NeonClient();
        };
    }

    // Expose globally
    window.sbNeon = neonClientInstance;
})();
