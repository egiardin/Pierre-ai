async function discoverImages(page) {
    return await page.evaluate(() => {
        const allCandidates = [];
        const photos = [];
        const logos = [];

        // Fonction pour identifier si un élément est un logo ou une icône
        const isLogoElement = (el) => {
            if (!el) return false;
            const src = el.src || el.href || '';
            const tagName = el.tagName ? el.tagName.toLowerCase() : '';
            const parent = el.closest('header, nav, footer, [itemprop="logo"], .logo, .brand, [class*="logo"], [class*="brand"]');
            
            if (parent || src.includes('.svg') || (el.rel && el.rel.includes('icon')) || tagName === 'svg') {
                return true;
            }
            const className = (el.className && typeof el.className === 'string') ? el.className.toLowerCase() : '';
            if (className.includes('logo') || className.includes('brand')) {
                return true;
            }
            return false;
        };

        // Collecte de tous les candidats possibles sans aucune limite
        const elements = document.querySelectorAll('img, svg, [style*="background-image"], source');
        elements.forEach(el => {
            let src = '';
            if (el.tagName === 'IMG') {
                src = el.src || el.dataset.src || el.currentSrc;
            } else if (el.tagName === 'SOURCE') {
                src = el.srcset;
            } else if (window.getComputedStyle(el).backgroundImage !== 'none') {
                const bg = window.getComputedStyle(el).backgroundImage;
                const match = bg.match(/url\(['"]?(.*?)['"]?\)/);
                if (match) src = match[1];
            }

            if (src && !src.startsWith('data:image/svg+xml')) {
                try {
                    const absoluteUrl = new URL(src, window.location.href).href;
                    const width = el.naturalWidth || el.width || 0;
                    const height = el.naturalHeight || el.height || 0;

                    // Conservation de la liste brute
                    allCandidates.push({
                        url: absoluteUrl,
                        width,
                        height
                    });

                    const isLogo = isLogoElement(el);
                    if (isLogo || absoluteUrl.endsWith('.svg')) {
                        logos.push({
                            url: absoluteUrl,
                            type: 'logo'
                        });
                    } else {
                        // Flux de photos avec contraintes de taille minimale standard
                        if (width === 0 || height === 0 || (width >= 100 && height >= 100)) {
                            photos.push({
                                url: absoluteUrl,
                                width,
                                height,
                                type: 'photo'
                            });
                        }
                    }
                } catch (e) {
                    // URL invalide ignorée
                }
            }
        });

        return {
            allCandidates,
            photos,
            logos
        };
    });
}

module.exports = { discoverImages };
