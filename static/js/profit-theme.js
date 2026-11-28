/* ProFit Gym Console — theme + shell behaviour */
(function () {
    'use strict';

    var root = document.documentElement;
    var THEME_KEY = 'pf-theme';
    var MINI_KEY = 'pf-sidebar-mini';

    function cssVar(name) {
        return getComputedStyle(root).getPropertyValue(name).trim();
    }

    /* ---------- Theme ---------- */
    function currentTheme() {
        return root.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
    }

    function applyTheme(theme, animate) {
        if (animate) {
            document.body.classList.add('pf-theme-anim');
            setTimeout(function () { document.body.classList.remove('pf-theme-anim'); }, 350);
        }
        root.setAttribute('data-bs-theme', theme);
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute('content', theme === 'dark' ? '#0C0C0D' : '#F5F5F2');
        document.querySelectorAll('[data-pf-theme-label]').forEach(function (el) {
            el.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
        });
        restyleCharts();
        document.dispatchEvent(new CustomEvent('pf:themechange', { detail: { theme: theme } }));
    }

    window.pfToggleTheme = function () {
        var next = currentTheme() === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* private mode */ }
        applyTheme(next, true);
    };

    /* ---------- Chart.js theming ---------- */
    window.pfChartColors = function () {
        return {
            gold: '#FFD700',
            orange: '#FF8C00',
            ink: cssVar('--pf-chart-line-2') || '#141414',
            neutral: cssVar('--pf-chart-neutral') || '#2A2A2A',
            grid: cssVar('--pf-chart-grid') || 'rgba(0,0,0,.06)',
            text: cssVar('--pf-chart-text') || '#5B626A',
            surface: cssVar('--pf-surface') || '#fff',
            border: cssVar('--pf-border') || '#e5e5e5',
            success: cssVar('--pf-success'),
            danger: cssVar('--pf-danger'),
            info: cssVar('--pf-info'),
            palette: ['#FFB800', '#FF8C00', '#22C55E', '#3B82F6', '#A855F7', '#EF4444', '#14B8A6', '#94A3B8']
        };
    };

    function setChartDefaults() {
        if (!window.Chart || !Chart.defaults) return;
        var c = window.pfChartColors();
        Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
        Chart.defaults.font.weight = 500;
        Chart.defaults.color = c.text;
        Chart.defaults.borderColor = c.grid;
        if (Chart.defaults.plugins && Chart.defaults.plugins.tooltip) {
            var t = Chart.defaults.plugins.tooltip;
            t.backgroundColor = '#141414';
            t.titleColor = '#FFD700';
            t.bodyColor = '#fff';
            t.padding = 12;
            t.cornerRadius = 10;
            t.displayColors = false;
            t.titleFont = { weight: 700 };
        }
        if (Chart.defaults.plugins && Chart.defaults.plugins.legend) {
            Chart.defaults.plugins.legend.labels.usePointStyle = true;
            Chart.defaults.plugins.legend.labels.boxWidth = 8;
        }
    }

    function restyleCharts() {
        if (!window.Chart) return;
        setChartDefaults();
        var c = window.pfChartColors();
        var instances = Chart.instances ? Object.values(Chart.instances) : [];
        instances.forEach(function (chart) {
            var scales = chart.options.scales || {};
            Object.keys(scales).forEach(function (k) {
                var s = scales[k];
                if (s.ticks) s.ticks.color = c.text;
                if (s.grid && s.grid.display !== false) s.grid.color = c.grid;
                if (s.border) s.border.color = c.grid;
            });
            if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
                chart.options.plugins.legend.labels.color = c.text;
            }
            // datasets flagged with pfInk follow the theme's ink/foreground colour
            chart.data.datasets.forEach(function (ds) {
                if (ds.pfInk) {
                    ds.borderColor = c.ink;
                    ds.pointBorderColor = c.ink;
                }
                if (ds.pfSurfaceBorder) ds.borderColor = c.surface;
                if (ds.pfNeutral) ds.backgroundColor = c.neutral;
            });
            chart.update('none');
        });
    }
    window.pfRestyleCharts = restyleCharts;

    /* ---------- Sidebar ---------- */
    window.pfToggleSidebar = function () {
        if (window.matchMedia('(min-width: 992px)').matches) {
            var mini = root.classList.toggle('pf-mini');
            try { localStorage.setItem(MINI_KEY, mini ? '1' : '0'); } catch (e) { /* ignore */ }
            setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 260);
        } else {
            root.classList.toggle('pf-drawer-open');
        }
    };
    window.pfCloseDrawer = function () { root.classList.remove('pf-drawer-open'); };

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') window.pfCloseDrawer();
        // "/" focuses the first search box on the page
        if (e.key === '/' && !/input|textarea|select/i.test(document.activeElement.tagName) && !document.activeElement.isContentEditable) {
            var s = document.querySelector('.dataTables_filter input, input[type="search"], input[name="q"], input[name="search"]');
            if (s) { e.preventDefault(); s.focus(); }
        }
    });

    /* ---------- Init on DOM ready ---------- */
    document.addEventListener('DOMContentLoaded', function () {
        setChartDefaults();

        // Close the drawer after navigating on mobile
        document.querySelectorAll('.pf-sidebar a[href]:not([data-bs-toggle])').forEach(function (a) {
            a.addEventListener('click', window.pfCloseDrawer);
        });

        // Keep the active nav item visible in long sidebars
        var active = document.querySelector('.pf-nav .pf-nav-link.active');
        if (active && active.scrollIntoView) active.scrollIntoView({ block: 'nearest' });

        // Tooltips for mini-sidebar
        if (window.bootstrap && bootstrap.Tooltip) {
            document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
                new bootstrap.Tooltip(el);
            });
        }

        // DataTables friendlier defaults
        if (window.jQuery && jQuery.fn && jQuery.fn.dataTable) {
            jQuery.extend(true, jQuery.fn.dataTable.defaults, {
                language: {
                    search: '',
                    searchPlaceholder: 'Search…  (press /)',
                    lengthMenu: 'Show _MENU_',
                    info: 'Showing _START_–_END_ of _TOTAL_',
                    infoEmpty: 'No records',
                    emptyTable: 'Nothing here yet',
                    zeroRecords: 'No matching records found',
                    paginate: { previous: '<i class="bi bi-chevron-left"></i>', next: '<i class="bi bi-chevron-right"></i>' }
                }
            });
        }

        // Charts may be created after DOM ready (jQuery ready handlers); restyle once loaded
        window.addEventListener('load', function () { restyleCharts(); });
    });

    // Double-submit guard + loading state for buttons marked data-pf-loading
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || form.hasAttribute('data-pf-no-guard')) return;
        var btn = form.querySelector('button[type="submit"][data-pf-loading], button:not([type])[data-pf-loading]');
        if (btn && !e.defaultPrevented) {
            setTimeout(function () {
                btn.disabled = true;
                btn.dataset.pfOriginal = btn.innerHTML;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ' + (btn.getAttribute('data-pf-loading') || 'Please wait…');
            }, 0);
        }
    }, true);
})();
