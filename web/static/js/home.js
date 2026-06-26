document.addEventListener("DOMContentLoaded", (event) => {
    gsap.registerPlugin(ScrollTrigger);

    const titleSplit = new SplitType('.hero-title', { types: 'chars' });
    
    gsap.from(titleSplit.chars, {
        opacity: 0,
        y: 80,
        rotationX: -90,
        rotationY: 45,
        scale: 0.5,
        transformOrigin: "50% 50% -50",
        stagger: {
            amount: 0.8,
            from: "center"
        },
        duration: 1.2,
        ease: "expo.out",
        delay: 0.2
    });

    const tl = gsap.timeline();
    
    tl.to('.hero-desc', {
        y: 0,
        opacity: 1,
        duration: 0.8,
        ease: "power3.out",
        delay: 1
    })
    .to('.hero-section .store-buttons', {
        y: 0,
        opacity: 1,
        duration: 0.8,
        ease: "back.out(1.7)"
    }, "-=0.4")
    .to('.hero-socials', {
        y: 0,
        opacity: 1,
        duration: 0.8,
        ease: "back.out(1.5)"
    }, "-=0.5");

    gsap.to('.hero-bg', {
        yPercent: 30,
        ease: "none",
        scrollTrigger: {
            trigger: ".hero-section",
            start: "top top",
            end: "bottom top",
            scrub: true
        }
    });

    gsap.to('.section-header', {
        y: 0,
        opacity: 1,
        duration: 1,
        scrollTrigger: {
            trigger: ".features-section",
            start: "top 80%"
        }
    });

    gsap.from('.carousel-container', {
        y: 100,
        opacity: 0,
        duration: 1,
        ease: "power3.out",
        scrollTrigger: {
            trigger: ".features-section",
            start: "top 75%"
        }
    });

    const track = document.getElementById('carouselTrack');
    const cards = document.querySelectorAll('.feature-card');

    if (track) {
        track.addEventListener('dragstart', (e) => e.preventDefault());
    }
    
    if (track && cards.length > 0) {
        let currentIndex = 0;
        const totalCards = cards.length;

        const updateCoverflow = () => {
            const isMobile = window.innerWidth <= 768;
            const spacing = isMobile ? 110 : 180;

            cards.forEach((card, index) => {
                let offset = index - currentIndex;
                
                if (offset > Math.floor(totalCards / 2)) {
                    offset -= totalCards;
                } else if (offset < -Math.floor(totalCards / 2)) {
                    offset += totalCards;
                }

                const direction = Math.sign(offset);
                const absOffset = Math.abs(offset);

                let scale = 1;
                let translateX = offset * spacing;
                let translateZ = 0;
                let rotateY = 0;
                let opacity = 1;
                let zIndex = 100 - absOffset;

                if (absOffset === 0) {
                    scale = 1;
                    translateZ = 50;
                    rotateY = 0;
                    opacity = 1;
                    card.classList.add('active');
                } else {
                    scale = 0.8 - (absOffset * 0.05);
                    translateZ = -100 - (absOffset * 100);
                    rotateY = direction * -35;
                    opacity = absOffset > 2 ? 0 : 1 - (absOffset * 0.2);
                    card.classList.remove('active');
                }

                card.style.zIndex = zIndex;
                card.style.opacity = opacity;
                card.style.transform = `translateX(${translateX}px) translateZ(${translateZ}px) rotateY(${rotateY}deg) scale(${scale})`;
            });
        };

        const btnNext = document.getElementById('btnNext');
        const btnPrev = document.getElementById('btnPrev');

        if (btnNext) {
            btnNext.addEventListener('click', () => {
                currentIndex = (currentIndex + 1) % totalCards;
                updateCoverflow();
            });
        }
        
        if (btnPrev) {
            btnPrev.addEventListener('click', () => {
                currentIndex = (currentIndex - 1 + totalCards) % totalCards;
                updateCoverflow();
            });
        }

        cards.forEach((card, index) => {
            card.addEventListener('click', () => {
                currentIndex = index;
                updateCoverflow();
            });
        });

        let isDragging = false;
        let startPos = 0;
        let isSwiping = false;

        const dragStart = (e) => {
            isDragging = true;
            isSwiping = false;
            startPos = e.type.includes('mouse') ? e.pageX : e.touches[0].clientX;
            track.classList.add('dragging');
        };

        const dragEnd = (e) => {
            if (!isDragging) return;
            isDragging = false;
            track.classList.remove('dragging');
            
            const endPos = e.type.includes('mouse') ? e.pageX : e.changedTouches[0].clientX;
            const diff = startPos - endPos;
            
            if (Math.abs(diff) > 40) {
                isSwiping = true; 
                if (diff > 0) {
                    currentIndex = (currentIndex + 1) % totalCards;
                } else {
                    currentIndex = (currentIndex - 1 + totalCards) % totalCards;
                }
                updateCoverflow();
                
                setTimeout(() => isSwiping = false, 100);
            }
        };

        track.addEventListener('mousedown', dragStart);
        track.addEventListener('mouseup', dragEnd);
        track.addEventListener('mouseleave', dragEnd);
        track.addEventListener('mousemove', (e) => {
            if(isDragging) e.preventDefault();
        });

        track.addEventListener('touchstart', dragStart, {passive: true});
        track.addEventListener('touchend', dragEnd, {passive: true});
        
        cards.forEach((card, index) => {
            card.addEventListener('click', (e) => {
                if (isSwiping) {
                    e.preventDefault();
                    return;
                }
                currentIndex = index;
                updateCoverflow();
            });
        });

        window.addEventListener('resize', updateCoverflow);
        updateCoverflow();
    }

    const zoomBtns = document.querySelectorAll('.card-zoom-btn');
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImg');
    const modalClose = document.getElementById('modalClose');

    if (zoomBtns.length > 0 && modal && modalImg) {
        zoomBtns.forEach(btn => {
            ['click', 'mousedown', 'touchstart'].forEach(eventType => {
                btn.addEventListener(eventType, (e) => e.stopPropagation());
            });

            btn.addEventListener('click', () => {
                const card = btn.closest('.feature-card');
                const img = card.querySelector('.feature-img');
                
                modalImg.src = img.src;
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            });
        });

        const closeModal = () => {
            modal.classList.remove('active');
            document.body.style.overflow = '';
            setTimeout(() => { modalImg.src = ''; }, 400);
        };

        if (modalClose) {
            modalClose.addEventListener('click', closeModal);
        }
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) closeModal();
        });
    }

    gsap.from('.manifesto-text h2, .manifesto-text p', {
        x: -50,
        opacity: 0,
        duration: 1,
        stagger: 0.2,
        ease: "power3.out",
        scrollTrigger: {
            trigger: ".manifesto-section",
            start: "top 70%"
        }
    });

    const glassPanel = document.querySelector('.glass-panel');
    if (window.innerWidth > 1024 && glassPanel) {
        gsap.to(glassPanel, {
            yPercent: -15,
            ease: "none",
            scrollTrigger: {
                trigger: ".manifesto-section",
                start: "top bottom",
                end: "bottom top",
                scrub: true
            }
        });
    }

    gsap.from('.stat-card', {
        x: 50,
        opacity: 0,
        duration: 0.8,
        stagger: 0.2,
        ease: "back.out(1.5)",
        scrollTrigger: {
            trigger: ".glass-panel",
            start: "top 75%"
        }
    });

    gsap.to('.cta-bg-image', {
        yPercent: 20,
        ease: "none",
        scrollTrigger: {
            trigger: ".cta-section",
            start: "top bottom",
            end: "bottom top",
            scrub: true
        }
    });

    gsap.from('.cta-content h2', {
        y: 50,
        opacity: 0,
        duration: 1,
        scrollTrigger: {
            trigger: ".cta-section",
            start: "top 80%"
        }
    });

    gsap.to('.cta-content .store-buttons', {
        y: 0,
        opacity: 1,
        duration: 0.8,
        ease: "back.out(1.7)",
        scrollTrigger: {
            trigger: ".cta-section",
            start: "top 75%"
        }
    });

    gsap.from('.team-card', {
        y: 60,
        opacity: 0,
        duration: 1,
        ease: "power3.out",
        scrollTrigger: {
            trigger: ".team-section",
            start: "top 80%"
        }
    });

    gsap.from('.contact-container', {
        y: 50,
        opacity: 0,
        duration: 1,
        ease: "power3.out",
        scrollTrigger: {
            trigger: ".contact-section",
            start: "top 80%"
        }
    });

    const btnCopyEmail = document.getElementById('btnCopyEmail');
    const copyTooltip = document.getElementById('copyTooltip');

    if (btnCopyEmail && copyTooltip) {
        btnCopyEmail.addEventListener('click', () => {
            navigator.clipboard.writeText('contact@cartmaker.app').then(() => {
                copyTooltip.classList.add('show');
                setTimeout(() => { copyTooltip.classList.remove('show'); }, 2000);
            }).catch(err => console.error('Error al copiar el correo: ', err));
        });
    }

    const btnCopyWhatsApp = document.getElementById('btnCopyWhatsApp');
    const whatsappTooltip = document.getElementById('whatsappTooltip');

    if (btnCopyWhatsApp && whatsappTooltip) {
        btnCopyWhatsApp.addEventListener('click', () => {
            navigator.clipboard.writeText('+584222383498').then(() => {
                whatsappTooltip.classList.add('show');
                setTimeout(() => { whatsappTooltip.classList.remove('show'); }, 2000);
            }).catch(err => console.error('Error al copiar el WhatsApp: ', err));
        });
    }

    const navbar = document.querySelector('.public-navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.style.background = 'rgba(10, 6, 20, 0.98)';
                navbar.style.padding = '0 3%';
            } else {
                navbar.style.background = 'rgba(10, 6, 20, 0.6)';
                navbar.style.padding = '0 5%';
            }
        });
    }
});