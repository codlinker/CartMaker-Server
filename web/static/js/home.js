document.addEventListener("DOMContentLoaded", () => {
    const landingRoot = document.getElementById("landingRoot");
    const hasCommission = landingRoot ? landingRoot.dataset.hasCommission === "true" : true;
    const commissionPct = landingRoot ? (landingRoot.dataset.commissionPct || "2.5") : "2.5";
    const commissionNum = landingRoot ? parseFloat(landingRoot.dataset.commissionNum || "2.5") : 2.5;

    const commissionPillText = hasCommission
        ? `Crear tu comercio es 100% Gratis · Solo ${commissionPct}% de comisión por cada venta`
        : `Crear tu comercio y vender en tu zona es 100% Gratis ($0/mes)`;

    /* ==========================================================================
       1. HERO PERSONA SWITCHER (COMPRADOR / EMPRENDEDOR / LOCAL O EMPRESA)
       ========================================================================== */
    const personaData = {
        "buyer": {
            headline: 'Todo el comercio de <span class="text-gradient-clickup">tu zona</span> en tiempo real. A minutos de ti.',
            subheadline: 'Descubre en <strong>videos verticales de 30s</strong>, Mapa 3D y con <strong>Atlas IA</strong> qué tiendas, locales o emprendedores tienen exactamente lo que buscas en tu zona, con stock en vivo y precios claros en <strong>USD y Bs. (BCV)</strong>. <em>Quién sabe, capaz tu vecino vende lo que buscas.</em>',
            pills: [
                'Cero «¿Precio al DM?»: stock real, descuentos con Tokens y precios BCV al instante',
                '¿Vendes? Toma una foto y Atlas IA registra todo tu inventario en 15 segundos',
                commissionPillText
            ]
        },
        "home-seller": {
            headline: 'Crea tu tienda virtual <span class="text-gradient-clickup">100% gratis</span> y vende en toda tu zona.',
            subheadline: hasCommission
                ? `¿Vendes desde casa o por internet? Abre tu comercio en CartMaker con <strong>$0 de mensualidad</strong> (solo ${commissionPct}% cuando concretas una venta). Toma una foto y <strong>Atlas IA registra todo tu inventario en 15 segundos</strong>.`
                : `¿Vendes desde casa o por internet? Abre tu comercio y vende en toda tu zona <strong>100% gratis</strong>. Toma una foto y <strong>Atlas IA registra todo tu inventario en 15 segundos</strong>.`,
            pills: [
                commissionPillText,
                'Escaneo de inventario en 15s: Atlas IA reconoce tu foto y crea tus productos',
                'Sube videos verticales de 30s a CartMaker TV para destacar en tu zona'
            ]
        },
        "shop-seller": {
            headline: 'Conecta el inventario de tu local al <span class="text-gradient-clickup">radar de tu zona</span> en 15 segundos.',
            subheadline: 'Miles de clientes buscan en tu zona lo que hoy tienes en tu mostrador. Digitaliza tu catálogo en <strong>15 segundos con una foto gracias a Atlas IA</strong>, aparece en el Mapa 3D y despacha con cálculo de ruta GPS.',
            pills: [
                'En 15s registras todo tu inventario con la función «Agregar varios ✨» de Atlas IA',
                'Mapa 3D con pines en vivo + Logística de Despacho con ruta y tiempo en moto',
                'Protección KYB con RIF SENIAT Módulo-11, Registro Mercantil y Respuestas Rápidas'
            ]
        }
    };

    const personaTabs = document.querySelectorAll('.persona-tab');
    const heroHeadline = document.getElementById('heroHeadline');
    const heroSubheadline = document.getElementById('heroSubheadline');
    const pillText1 = document.getElementById('pillText1');
    const pillText2 = document.getElementById('pillText2');
    const pillText3 = document.getElementById('pillText3');

    personaTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const key = tab.dataset.persona;
            const data = personaData[key];
            if (!data) return;

            personaTabs.forEach(t => {
                t.classList.remove('active');
                t.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('active');
            tab.setAttribute('aria-selected', 'true');

            if (heroHeadline) heroHeadline.innerHTML = data.headline;
            if (heroSubheadline) heroSubheadline.innerHTML = data.subheadline;
            if (pillText1) pillText1.textContent = data.pills[0];
            if (pillText2) pillText2.textContent = data.pills[1];
            if (pillText3) pillText3.textContent = data.pills[2];
        });
    });

    /* ==========================================================================
       2. SIMULADOR INTERACTIVO DE ESCANEO DE INVENTARIO EN 15S (#inventario-ia)
       ========================================================================== */
    const scanStepCards = document.querySelectorAll('.scan-step-card');
    const btnTriggerScanDemo = document.getElementById('btnTriggerScanDemo');
    const scanTimerText = document.getElementById('scanTimerText');
    const scannerFrame = document.getElementById('scannerFrame');
    const scannerHudStatus = document.getElementById('scannerHudStatus');

    const stepHudMessages = {
        "1": "Paso 1/3 · Capturando foto de tus productos con «Agregar varios ✨»...",
        "2": "Paso 2/3 · Atlas IA reconociendo nombres, marcas y precios en la foto...",
        "3": "¡Completado en 15.0s! · Todos tus productos fueron creados automáticamente"
    };

    const activateScanStep = (stepStr) => {
        scanStepCards.forEach(card => {
            card.classList.toggle('active', card.dataset.scanStep === String(stepStr));
        });
        if (scannerHudStatus && stepHudMessages[stepStr]) {
            scannerHudStatus.textContent = stepHudMessages[stepStr];
        }
    };

    scanStepCards.forEach(card => {
        card.addEventListener('click', () => {
            activateScanStep(card.dataset.scanStep);
        });
    });

    let scanInterval = null;
    if (btnTriggerScanDemo) {
        btnTriggerScanDemo.addEventListener('click', () => {
            if (scanInterval) clearInterval(scanInterval);
            if (scannerFrame) scannerFrame.classList.add('scanning-fast');

            let elapsed = 0.0;
            activateScanStep("1");

            scanInterval = setInterval(() => {
                elapsed += 0.5;
                if (elapsed <= 4.0) {
                    activateScanStep("1");
                } else if (elapsed <= 11.5) {
                    activateScanStep("2");
                } else {
                    activateScanStep("3");
                }

                if (scanTimerText) {
                    scanTimerText.textContent = elapsed < 15.0
                        ? `Escaneando con Atlas IA... ${elapsed.toFixed(1)}s`
                        : `15.0s · ¡Inventario creado!`;
                }

                if (elapsed >= 15.0) {
                    clearInterval(scanInterval);
                    scanInterval = null;
                    if (scannerFrame) scannerFrame.classList.remove('scanning-fast');
                }
            }, 95);
        });
    }

    /* ==========================================================================
       3. PESTAÑAS INTERACTIVAS DEL ECOSISTEMA (CLICKUP WORKSPACE TABS)
       ========================================================================== */
    const wsTabBtns = document.querySelectorAll('.ws-tab-btn');
    const wsPanels = document.querySelectorAll('.ws-panel');

    wsTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetKey = btn.dataset.ws;

            wsTabBtns.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');

            wsPanels.forEach(panel => {
                panel.classList.toggle('active', panel.id === `ws-panel-${targetKey}`);
            });
        });
    });

    /* ==========================================================================
       4. GALERÍA INTERACTIVA DE 4 CAPTURAS REALES DE ATLAS IA (#atlas-ia)
       ========================================================================== */
    const atlasCaptions = [
        "Captura Real 1/4 · «¡Hola Atlas! Quiero mejorar mi computadora»",
        "Captura Real 2/4 · Comparativa RTX 5090, RAM DDR5, Ryzen 9 y estado de tienda",
        "Captura Real 3/4 · Tarjetas «MUY CERCA» con botón naranja de compra en el chat",
        "Captura Real 4/4 · Repuestos automotrices cercanos en Autopartes KRP C.A."
    ];

    let currentAtlasIndex = 0;
    const atlasPromptBtns = document.querySelectorAll('.atlas-prompt-btn');
    const atlasSlides = document.querySelectorAll('.atlas-slide');
    const atlasDots = document.querySelectorAll('.atlas-dot');
    const atlasSlideCaption = document.getElementById('atlasSlideCaption');
    const atlasPrevBtn = document.getElementById('atlasPrevBtn');
    const atlasNextBtn = document.getElementById('atlasNextBtn');

    const setAtlasSlide = (index) => {
        const total = atlasSlides.length;
        if (!total) return;
        currentAtlasIndex = (index + total) % total;

        atlasPromptBtns.forEach(btn => {
            btn.classList.toggle('active', Number(btn.dataset.atlasSlide) === currentAtlasIndex);
        });
        atlasSlides.forEach(slide => {
            slide.classList.toggle('active', Number(slide.dataset.slideIndex) === currentAtlasIndex);
        });
        atlasDots.forEach(dot => {
            dot.classList.toggle('active', Number(dot.dataset.atlasSlide) === currentAtlasIndex);
        });
        if (atlasSlideCaption && atlasCaptions[currentAtlasIndex]) {
            atlasSlideCaption.textContent = atlasCaptions[currentAtlasIndex];
        }
    };

    atlasPromptBtns.forEach(btn => {
        btn.addEventListener('click', () => setAtlasSlide(Number(btn.dataset.atlasSlide)));
    });

    atlasDots.forEach(dot => {
        dot.addEventListener('click', () => setAtlasSlide(Number(dot.dataset.atlasSlide)));
    });

    if (atlasPrevBtn) {
        atlasPrevBtn.addEventListener('click', () => setAtlasSlide(currentAtlasIndex - 1));
    }

    if (atlasNextBtn) {
        atlasNextBtn.addEventListener('click', () => setAtlasSlide(currentAtlasIndex + 1));
    }

    /* ==========================================================================
       5. CALCULADORA INTERACTIVA DE VENTAS Y COMISIÓN (#precios)
       ========================================================================== */
    const salesRangeSlider = document.getElementById('salesRangeSlider');
    const calcSalesDisplay = document.getElementById('calcSalesDisplay');
    const calcCommissionDisplay = document.getElementById('calcCommissionDisplay');
    const calcNetDisplay = document.getElementById('calcNetDisplay');

    const updateSalesCalculator = () => {
        if (!salesRangeSlider) return;
        const gross = parseFloat(salesRangeSlider.value || "1000");
        const commissionAmount = hasCommission ? (gross * (commissionNum / 100.0)) : 0.0;
        const netAmount = gross - commissionAmount;

        if (calcSalesDisplay) {
            calcSalesDisplay.textContent = `$${gross.toLocaleString('en-US')} USD`;
        }
        if (calcCommissionDisplay) {
            calcCommissionDisplay.textContent = `$${commissionAmount.toFixed(2)} USD`;
        }
        if (calcNetDisplay) {
            calcNetDisplay.textContent = `$${netAmount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
        }
    };

    if (salesRangeSlider) {
        salesRangeSlider.addEventListener('input', updateSalesCalculator);
        updateSalesCalculator();
    }

    /* ==========================================================================
       6. ACORDEÓN DE PREGUNTAS FRECUENTES (FAQ)
       ========================================================================== */
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach(item => {
        const btn = item.querySelector('.faq-question');
        if (!btn) return;

        btn.addEventListener('click', () => {
            const isOpen = item.classList.contains('active');
            faqItems.forEach(other => {
                other.classList.remove('active');
                const otherBtn = other.querySelector('.faq-question');
                if (otherBtn) otherBtn.setAttribute('aria-expanded', 'false');
            });

            if (!isOpen) {
                item.classList.add('active');
                btn.setAttribute('aria-expanded', 'true');
            }
        });
    });

    /* ==========================================================================
       7. MODAL LIGHTBOX PARA CAPTURAS DE LA APP
       ========================================================================== */
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImg');
    const modalClose = document.getElementById('modalClose');
    const zoomBtns = document.querySelectorAll('.btn-zoom-preview');
    const zoomableImgs = document.querySelectorAll('.zoomable-img');

    const openLightbox = (src) => {
        if (!modal || !modalImg || !src) return;
        modalImg.src = src;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    };

    const closeLightbox = () => {
        if (!modal || !modalImg) return;
        modal.classList.remove('active');
        document.body.style.overflow = '';
        setTimeout(() => { modalImg.src = ''; }, 250);
    };

    zoomBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            openLightbox(btn.dataset.img);
        });
    });

    zoomableImgs.forEach(img => {
        img.addEventListener('click', () => openLightbox(img.src));
    });

    if (modalClose) {
        modalClose.addEventListener('click', closeLightbox);
    }

    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeLightbox();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
            closeLightbox();
        }
    });

    /* ==========================================================================
       8. SCROLL REVEAL & EFECTO 3D TILT EN TARJETAS (DESKTOP)
       ========================================================================== */
    const revealSections = document.querySelectorAll('.reveal-on-scroll');
    if ('IntersectionObserver' in window && revealSections.length) {
        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        revealSections.forEach(sec => revealObserver.observe(sec));
    } else {
        revealSections.forEach(sec => sec.classList.add('is-visible'));
    }

    if (window.matchMedia('(min-width: 1024px) and (hover: hover)').matches) {
        const tiltCards = document.querySelectorAll('[data-tilt-card]');
        tiltCards.forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                const rotateX = ((y - centerY) / centerY) * -2.8;
                const rotateY = ((x - centerX) / centerX) * 2.8;
                card.style.transform = `perspective(900px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-3px)`;
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
            });
        });
    }
});