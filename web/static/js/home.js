/* ==========================================================================
   CARTMAKER — LANDING PARA CLIENTES · interactividad
   Vanilla JS, sin dependencias. Todo respeta "reducir movimiento".
   ========================================================================== */
(function () {
    'use strict';

    var root = document.getElementById('landingRoot');
    if (!root) return;

    var $ = function (sel, ctx) { return (ctx || document).querySelector(sel); };
    var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    /** Ejecuta `cb` una sola vez cuando `el` entra en pantalla. */
    function onceVisible(el, cb, threshold) {
        if (!el) return;
        if (!('IntersectionObserver' in window)) { cb(); return; }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) { io.disconnect(); cb(); }
            });
        }, { threshold: threshold || 0.25 });
        io.observe(el);
    }

    /** Observa visibilidad continua (entra / sale). */
    function watchVisible(el, cb, threshold) {
        if (!el) return;
        if (!('IntersectionObserver' in window)) { cb(true); return; }
        new IntersectionObserver(function (entries) {
            entries.forEach(function (e) { cb(e.isIntersecting); });
        }, { threshold: threshold || 0.35 }).observe(el);
    }

    /* ----------------------------------------------------------------------
       1. Revelado al hacer scroll (con escalonado entre hermanos)
       ---------------------------------------------------------------------- */
    (function initReveal() {
        var items = $$('.reveal', root);
        var groups = new Map();
        items.forEach(function (el) {
            var p = el.parentElement;
            if (!groups.has(p)) groups.set(p, []);
            groups.get(p).push(el);
        });
        groups.forEach(function (list) {
            list.forEach(function (el, i) { el.style.setProperty('--d', Math.min(i, 4) * 90 + 'ms'); });
        });
        if (!('IntersectionObserver' in window) || reduceMotion) {
            items.forEach(function (el) { el.classList.add('is-in'); });
            return;
        }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (!e.isIntersecting) return;
                var el = e.target;
                el.classList.add('is-in');
                io.unobserve(el);
                // Al terminar la animación se libera el elemento para que sus efectos propios (hover) funcionen
                var delay = parseInt(el.style.getPropertyValue('--d'), 10) || 0;
                setTimeout(function () {
                    el.classList.remove('reveal', 'is-in');
                    el.style.removeProperty('--d');
                }, 900 + delay + 150);
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
        items.forEach(function (el) { io.observe(el); });
    })();

    /* ----------------------------------------------------------------------
       2. Barra de progreso, menú activo y barra fija móvil
       ---------------------------------------------------------------------- */
    (function initScroll() {
        var bar = $('#scrollProgress');
        var sticky = $('#stickyCta');
        var heroCta = $('#descargar');
        var finalCta = $('#empezar');
        var navLinks = $$('.public-navbar .nav-item');
        var sections = ['comprar', 'atlas-ia', 'vender', 'seguridad', 'precios', 'faq']
            .map(function (id) { return document.getElementById(id); }).filter(Boolean);
        var heroVisible = true, finalVisible = false, ticking = false;

        function updateSticky() {
            if (!sticky) return;
            var show = window.scrollY > 240 && !heroVisible && !finalVisible;
            sticky.classList.toggle('is-visible', show);
            sticky.setAttribute('aria-hidden', show ? 'false' : 'true');
        }

        function update() {
            ticking = false;
            var h = document.documentElement;
            var max = h.scrollHeight - window.innerHeight;
            if (bar) bar.style.setProperty('--p', max > 0 ? (window.scrollY / max).toFixed(4) : 0);

            var current = null;
            var mid = window.scrollY + window.innerHeight * 0.35;
            sections.forEach(function (s) { if (s.offsetTop <= mid) current = s.id; });
            navLinks.forEach(function (a) {
                a.classList.toggle('is-current', !!current && a.getAttribute('href') === '#' + current);
            });
            updateSticky();
        }

        window.addEventListener('scroll', function () {
            if (!ticking) { ticking = true; requestAnimationFrame(update); }
        }, { passive: true });
        window.addEventListener('resize', update);

        watchVisible(heroCta, function (v) { heroVisible = v; updateSticky(); }, 0.2);
        watchVisible(finalCta, function (v) { finalVisible = v; updateSticky(); }, 0.15);
        update();
    })();

    /* ----------------------------------------------------------------------
       3. Selector "Quiero comprar / Quiero vender"
       ---------------------------------------------------------------------- */
    var setPersona = (function initPersona() {
        var tabs = $$('#personaSwitch .segmented-btn');
        var mainLabel = $('#stickyMainLabel');
        var stickyMain = $('.sticky-main');
        var stickyAlt = $('#stickyAlt');

        function apply(p) {
            root.dataset.persona = p;
            tabs.forEach(function (t) {
                var on = t.dataset.persona === p;
                t.classList.toggle('is-active', on);
                t.setAttribute('aria-selected', on ? 'true' : 'false');
                t.tabIndex = on ? 0 : -1;
            });
            $$('.persona-pane', root).forEach(function (el) {
                var on = el.dataset.pane === p;
                el.classList.toggle('is-active', on);
                el.setAttribute('aria-hidden', on ? 'false' : 'true');
                if (el.tagName === 'A') el.tabIndex = on ? 0 : -1;
            });
            $$('.hero-phone .shot[data-pane]').forEach(function (s) {
                s.classList.toggle('is-active', s.dataset.pane === p);
            });
            if (p === 'seller') {
                if (mainLabel) mainLabel.textContent = 'Crear mi tienda gratis';
                if (stickyMain) stickyMain.setAttribute('href', '#descargar');
                if (stickyAlt) { stickyAlt.setAttribute('href', '#precios'); stickyAlt.lastElementChild.textContent = 'Ver precios'; stickyAlt.firstElementChild.textContent = 'sell'; }
            } else {
                if (mainLabel) mainLabel.textContent = 'Descargar app';
                if (stickyMain) stickyMain.setAttribute('href', '#descargar');
                if (stickyAlt) { stickyAlt.setAttribute('href', '#vender'); stickyAlt.lastElementChild.textContent = 'Vender gratis'; stickyAlt.firstElementChild.textContent = 'storefront'; }
            }
        }

        tabs.forEach(function (t, i) {
            t.addEventListener('click', function () { apply(t.dataset.persona); });
            t.addEventListener('keydown', function (e) {
                if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                    var next = tabs[(i + 1) % tabs.length];
                    next.focus(); apply(next.dataset.persona); e.preventDefault();
                }
            });
        });

        // Quien llega por un enlace de vendedor ve primero el mensaje de vendedor
        var h = window.location.hash;
        if (h === '#vender' || h === '#fundadores') apply('seller');
        else apply('buyer');

        // Los enlaces "Vender gratis" cambian el mensaje del hero
        $$('a[href="#vender"], a[href="#fundadores"]').forEach(function (a) {
            a.addEventListener('click', function () { apply('seller'); });
        });
        return apply;
    })();

    /* ----------------------------------------------------------------------
       4. Comparación: hoy vs con CartMaker
       ---------------------------------------------------------------------- */
    (function initCompare() {
        var sw = $('#compareSwitch');
        var grid = $('#compareGrid');
        if (!sw || !grid) return;
        var btns = $$('.switch-btn', sw);
        var userTouched = false;

        function setMode(mode) {
            grid.dataset.mode = mode;
            sw.classList.toggle('is-after', mode === 'after');
            btns.forEach(function (b) {
                var on = b.dataset.mode === mode;
                b.classList.toggle('is-active', on);
                b.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
        }

        btns.forEach(function (b) {
            b.addEventListener('click', function () { userTouched = true; setMode(b.dataset.mode); });
        });

        if (reduceMotion) return;
        // Efecto de entrada: primero se muestra "hoy" y, al verlo, cambia solo a "con CartMaker"
        grid.classList.add('no-anim');
        setMode('before');
        requestAnimationFrame(function () { requestAnimationFrame(function () { grid.classList.remove('no-anim'); }); });
        onceVisible(grid, function () {
            setTimeout(function () { if (!userTouched) setMode('after'); }, 1700);
        }, 0.35);
    })();

    /* ----------------------------------------------------------------------
       5. Atlas: conversación de ejemplo con efecto de escritura
       ---------------------------------------------------------------------- */
    (function initAtlas() {
        var chips = $$('#promptChips .prompt-chip');
        var userBubble = $('#atlasUserBubble');
        var botBubble = $('#atlasBotBubble');
        var shots = $$('#atlasScreen .shot');
        if (!chips.length || !userBubble || !botBubble) return;

        var token = 0, timer = null, autoTimer = null, stopped = false, current = 0;

        function showShot(i) {
            shots.forEach(function (s) { s.classList.toggle('is-active', Number(s.dataset.shot) === i); });
        }

        function run(i) {
            var chip = chips[i];
            token += 1;
            var my = token;
            clearTimeout(timer);
            current = i;
            chips.forEach(function (c, k) {
                c.classList.toggle('is-active', k === i);
                c.setAttribute('aria-selected', k === i ? 'true' : 'false');
            });
            userBubble.textContent = chip.dataset.user;
            var text = chip.dataset.bot || '';

            if (reduceMotion) { botBubble.textContent = text; showShot(i); return; }

            botBubble.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
            timer = setTimeout(function () {
                if (my !== token) return;
                showShot(i);
                botBubble.innerHTML = '<span class="txt"></span><span class="caret"></span>';
                var out = $('.txt', botBubble);
                var n = 0;
                (function tick() {
                    if (my !== token) return;
                    n += 2;
                    out.textContent = text.slice(0, n);
                    if (n < text.length) { timer = setTimeout(tick, 18); }
                    else { var c = $('.caret', botBubble); if (c) c.remove(); }
                })();
            }, 950);
        }

        chips.forEach(function (c, i) {
            c.addEventListener('click', function () { stopped = true; clearInterval(autoTimer); run(i); });
        });

        onceVisible($('#atlasChat'), function () {
            run(0);
            if (reduceMotion) return;
            autoTimer = setInterval(function () {
                if (stopped) return;
                run((current + 1) % chips.length);
            }, 11000);
        }, 0.4);
    })();

    /* ----------------------------------------------------------------------
       6. Videos en bucle optimizados + visor de capturas y videos
       ---------------------------------------------------------------------- */
    function ensureLoopVideoPlaying(vid) {
        if (!vid) return;
        vid.muted = true;
        vid.defaultMuted = true;
        vid.playsInline = true;
        var p = vid.play();
        if (p && typeof p.catch === 'function') p.catch(function () {});
    }

    (function initLoopVideos() {
        var loopVideos = $$('.autoplay-loop-video', root);
        loopVideos.forEach(ensureLoopVideoPlaying);
        if ('IntersectionObserver' in window && loopVideos.length) {
            var videoObserver = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    var vid = entry.target;
                    if (entry.isIntersecting) ensureLoopVideoPlaying(vid);
                    else vid.pause();
                });
            }, { threshold: 0.15 });
            loopVideos.forEach(function (vid) { videoObserver.observe(vid); });
        }
    })();

    var lightbox = (function initLightbox() {
        var box = $('#lightbox');
        var img = $('#lightboxImg');
        var video = $('#lightboxVideo');
        var closeBtn = $('#lightboxClose');
        var lastFocus = null;
        if (!box || !img) return { open: function () {} };

        function isVideoSrc(src) {
            return /\.(mp4|webm|mov)(\?.*)?$/i.test(src || '');
        }

        function open(src, alt) {
            if (!src) return;
            lastFocus = document.activeElement;
            if (isVideoSrc(src) && video) {
                img.hidden = true;
                img.src = '';
                video.hidden = false;
                video.src = src;
                ensureLoopVideoPlaying(video);
            } else {
                if (video) {
                    video.pause();
                    video.hidden = true;
                    video.src = '';
                }
                img.hidden = false;
                img.src = src;
                img.alt = alt || 'Captura de CartMaker';
            }
            box.hidden = false;
            requestAnimationFrame(function () { box.classList.add('is-open'); });
            document.body.style.overflow = 'hidden';
            if (closeBtn) closeBtn.focus();
        }
        function close() {
            box.classList.remove('is-open');
            document.body.style.overflow = '';
            if (video) video.pause();
            setTimeout(function () {
                box.hidden = true;
                img.src = '';
                if (video) video.src = '';
            }, 350);
            if (lastFocus && lastFocus.focus) lastFocus.focus();
        }
        box.addEventListener('click', function (e) { if (e.target !== img && e.target !== video) close(); });
        if (closeBtn) closeBtn.addEventListener('click', close);
        document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !box.hidden) close(); });
        return { open: open, close: close };
    })();

    var swallowClick = false; // evita abrir el visor tras deslizar

    function openZoomFrom(el) {
        if (el.tagName === 'VIDEO' || el.dataset.videoSrc) {
            lightbox.open(el.dataset.videoSrc || el.currentSrc || el.getAttribute('src'), el.getAttribute('aria-label'));
            return;
        }
        var img = $('img', el);
        if (img) lightbox.open(img.getAttribute('src'), img.getAttribute('alt'));
    }

    $$('[data-zoom]', root).forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (swallowClick) { swallowClick = false; return; }
            if (e.target.closest && e.target.closest('.hotspot')) return;
            openZoomFrom(el);
        });
    });

    (function initFlows() {
        $$('[data-flow]', root).forEach(function (flow) {
            var steps = $$('.flow-step', flow);
            var shots = $$('.flow-stage .shot', flow);
            var dots = $$('.flow-dots i', flow);
            var stage = $('.flow-stage', flow);
            var screen = $('.phone-screen', flow);
            var autoMs = parseInt(flow.dataset.autoplay, 10) || 7000;
            var current = 0, timer = null, visible = false, userStopped = false, hoverStage = false, openTimer = null;
            flow.style.setProperty('--autoplay', autoMs + 'ms');

            // Descripción del paso sobre el teléfono (en móvil las pestañas solo muestran el número)
            var caps = [];
            if (stage) {
                var capsBox = document.createElement('div');
                capsBox.className = 'flow-captions';
                capsBox.setAttribute('aria-live', 'polite');
                steps.forEach(function (s, k) {
                    var titleEl = $('.flow-step-title', s), textEl = $('.flow-step-text', s);
                    var cap = document.createElement('div');
                    cap.className = 'flow-cap' + (k === 0 ? ' is-active' : '');
                    cap.innerHTML = '<strong></strong><p></p>';
                    $('strong', cap).textContent = titleEl ? titleEl.textContent : '';
                    $('p', cap).innerHTML = textEl ? textEl.innerHTML : '';
                    capsBox.appendChild(cap);
                    caps.push(cap);
                    s.setAttribute('aria-label', 'Paso ' + (k + 1) + ': ' + (titleEl ? titleEl.textContent : ''));
                });
                stage.insertBefore(capsBox, stage.firstChild);
            }

            function closeHotspots() {
                $$('.hotspot', flow).forEach(function (h) { h.classList.remove('is-open'); h.setAttribute('aria-expanded', 'false'); });
            }

            function openFirstHotspot(i) {
                clearTimeout(openTimer);
                openTimer = setTimeout(function () {
                    var h = $('.hotspot', shots[i]);
                    if (h && !$('.hotspot.is-open', flow)) { h.classList.add('is-open'); h.setAttribute('aria-expanded', 'true'); }
                }, 750);
            }

            function schedule() {
                clearTimeout(timer);
                flow.classList.remove('is-playing');
                if (reduceMotion || userStopped || !visible || hoverStage) return;
                void flow.offsetWidth; // reinicia la animación de la barra de progreso
                flow.classList.add('is-playing');
                timer = setTimeout(function () { go((current + 1) % steps.length, false); }, autoMs);
            }

            function go(i, fromUser) {
                current = i;
                steps.forEach(function (s, k) {
                    var on = k === i;
                    s.classList.toggle('is-active', on);
                    s.setAttribute('aria-selected', on ? 'true' : 'false');
                    s.tabIndex = on ? 0 : -1;
                });
                shots.forEach(function (s, k) { s.classList.toggle('is-active', k === i); });
                caps.forEach(function (c, k) { c.classList.toggle('is-active', k === i); });
                dots.forEach(function (d, k) { d.classList.toggle('is-active', k === i); });
                closeHotspots();
                openFirstHotspot(i);
                if (fromUser) userStopped = true;
                schedule();
            }

            steps.forEach(function (s, i) {
                s.addEventListener('click', function () { go(i, true); });
                s.addEventListener('keydown', function (e) {
                    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') { go((i + 1) % steps.length, true); steps[(i + 1) % steps.length].focus(); e.preventDefault(); }
                    if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') { var p = (i - 1 + steps.length) % steps.length; go(p, true); steps[p].focus(); e.preventDefault(); }
                });
            });

            // Puntos de ayuda: tocar abre / cierra la explicación
            $$('.hotspot', flow).forEach(function (h) {
                h.addEventListener('click', function (e) {
                    e.stopPropagation();
                    var willOpen = !h.classList.contains('is-open');
                    closeHotspots();
                    if (willOpen) { h.classList.add('is-open'); h.setAttribute('aria-expanded', 'true'); }
                    userStopped = true; schedule();
                });
            });
            document.addEventListener('click', function (e) {
                if (!e.target.closest || !e.target.closest('.hotspot')) closeHotspots();
            });

            // Deslizar el teléfono para cambiar de paso
            if (screen) {
                var sx = 0, sy = 0, tracking = false;
                screen.addEventListener('pointerdown', function (e) { tracking = true; sx = e.clientX; sy = e.clientY; });
                screen.addEventListener('pointerup', function (e) {
                    if (!tracking) return;
                    tracking = false;
                    var dx = e.clientX - sx, dy = e.clientY - sy;
                    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.4) {
                        swallowClick = true;
                        setTimeout(function () { swallowClick = false; }, 300);
                        go(dx < 0 ? (current + 1) % steps.length : (current - 1 + steps.length) % steps.length, true);
                    }
                });
                screen.addEventListener('pointercancel', function () { tracking = false; });
            }

            // Pausa mientras el cursor está sobre el teléfono
            if (stage && finePointer) {
                stage.addEventListener('mouseenter', function () { hoverStage = true; schedule(); });
                stage.addEventListener('mouseleave', function () { hoverStage = false; schedule(); });
            }

            watchVisible(flow, function (v) {
                visible = v;
                if (v && !$('.hotspot.is-open', flow)) openFirstHotspot(current);
                schedule();
            }, 0.4);
        });
    })();

    /* ----------------------------------------------------------------------
       7. Seguridad: "¿Qué te preocupa?" + pedido protegido animado
       ---------------------------------------------------------------------- */
    (function initWorry() {
        var chips = $$('#worryChips .worry-chip');
        var cards = $$('#worryAnswers .worry-card');
        if (!chips.length) return;

        function show(i) {
            chips.forEach(function (c, k) {
                c.classList.toggle('is-active', k === i);
                c.setAttribute('aria-selected', k === i ? 'true' : 'false');
                c.tabIndex = k === i ? 0 : -1;
            });
            cards.forEach(function (c, k) {
                if (k === i) { c.hidden = false; } else { c.hidden = true; }
            });
        }
        chips.forEach(function (c, i) {
            c.addEventListener('click', function () { show(i); });
            c.addEventListener('keydown', function (e) {
                if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                    var n = (i + (e.key === 'ArrowRight' ? 1 : chips.length - 1)) % chips.length;
                    chips[n].focus(); show(n); e.preventDefault();
                }
            });
        });
    })();

    (function initOrderDemo() {
        var demo = $('#orderDemo');
        if (!demo) return;
        var msgs = $$('.od-msg', demo);
        var timers = [];
        function reset() { timers.forEach(clearTimeout); timers = []; msgs.forEach(function (m) { m.classList.remove('is-in'); }); }
        function play() {
            reset();
            msgs.forEach(function (m, i) {
                if (reduceMotion) { m.classList.add('is-in'); return; }
                timers.push(setTimeout(function () { m.classList.add('is-in'); }, 500 + i * 1050));
            });
        }
        onceVisible(demo, play, 0.4);
        demo.addEventListener('click', play);
    })();

    /* ----------------------------------------------------------------------
       8. Calculadora de ventas (precios)
       ---------------------------------------------------------------------- */
    (function initCalc() {
        var slider = $('#salesRangeSlider');
        if (!slider) return;
        var salesEl = $('#calcSalesDisplay');
        var commEl = $('#calcCommissionDisplay');
        var netEl = $('#calcNetDisplay');
        var pct = parseFloat(root.dataset.commissionNum) || 0;
        var hasComm = root.dataset.hasCommission === 'true' && pct > 0;
        var money = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        var shown = { comm: 0, net: 0 }, raf = null;

        function paint(sales) {
            var comm = hasComm ? sales * pct / 100 : 0;
            var net = sales - comm;
            if (salesEl) salesEl.textContent = '$' + sales.toLocaleString('en-US') + ' USD';
            var from = { comm: shown.comm, net: shown.net };
            var start = null;
            cancelAnimationFrame(raf);
            function step(ts) {
                if (start === null) start = ts;
                var t = reduceMotion ? 1 : Math.min(1, (ts - start) / 380);
                var e = 1 - Math.pow(1 - t, 3);
                shown.comm = from.comm + (comm - from.comm) * e;
                shown.net = from.net + (net - from.net) * e;
                if (commEl) commEl.textContent = '$' + money.format(shown.comm) + ' USD';
                if (netEl) netEl.textContent = '$' + money.format(shown.net) + ' USD';
                if (t < 1) raf = requestAnimationFrame(step);
            }
            raf = requestAnimationFrame(step);
        }

        function onInput() {
            var v = parseInt(slider.value, 10) || 0;
            var min = parseInt(slider.min, 10), max = parseInt(slider.max, 10);
            slider.style.setProperty('--fill', ((v - min) / (max - min) * 100).toFixed(1) + '%');
            paint(v);
        }
        slider.addEventListener('input', onInput);
        var initial = parseInt(slider.value, 10) || 0;
        shown.comm = hasComm ? initial * pct / 100 : 0;
        shown.net = initial - shown.comm;
        slider.style.setProperty('--fill', (((initial - slider.min) / (slider.max - slider.min)) * 100).toFixed(1) + '%');
    })();

    /* ----------------------------------------------------------------------
       9. Preguntas frecuentes (acordeón)
       ---------------------------------------------------------------------- */
    (function initFaq() {
        var items = $$('.faq-item');
        items.forEach(function (item) {
            var q = $('.faq-q', item);
            if (!q) return;
            q.addEventListener('click', function () {
                var open = !item.classList.contains('is-open');
                items.forEach(function (o) {
                    o.classList.remove('is-open');
                    var b = $('.faq-q', o); if (b) b.setAttribute('aria-expanded', 'false');
                });
                if (open) { item.classList.add('is-open'); q.setAttribute('aria-expanded', 'true'); }
            });
        });
    })();

    /* ----------------------------------------------------------------------
       10. Efectos de puntero (solo escritorio): inclinación, foco y imán
       ---------------------------------------------------------------------- */
    (function initPointerFx() {
        // El foco de luz también funciona con el dedo
        $$('.spot', root).forEach(function (el) {
            el.addEventListener('pointermove', function (e) {
                var r = el.getBoundingClientRect();
                el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
                el.style.setProperty('--my', (e.clientY - r.top) + 'px');
            }, { passive: true });
        });

        if (!finePointer || reduceMotion) return;

        $$('[data-tilt]', root).forEach(function (stage) {
            var phone = $('.phone', stage);
            if (!phone) return;
            stage.addEventListener('mousemove', function (e) {
                var r = stage.getBoundingClientRect();
                var x = (e.clientX - r.left) / r.width - 0.5;
                var y = (e.clientY - r.top) / r.height - 0.5;
                phone.style.setProperty('--ry', (x * 14).toFixed(2) + 'deg');
                phone.style.setProperty('--rx', (-y * 10).toFixed(2) + 'deg');
            });
            stage.addEventListener('mouseleave', function () {
                phone.style.setProperty('--ry', '0deg');
                phone.style.setProperty('--rx', '0deg');
            });
        });

        $$('[data-magnetic]', root).forEach(function (btn) {
            btn.addEventListener('mousemove', function (e) {
                var r = btn.getBoundingClientRect();
                var x = (e.clientX - (r.left + r.width / 2)) * 0.18;
                var y = (e.clientY - (r.top + r.height / 2)) * 0.28;
                btn.style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)';
            });
            btn.addEventListener('mouseleave', function () { btn.style.transform = ''; });
        });
    })();
})();
