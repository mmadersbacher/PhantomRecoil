// State
let currentTab = 'attackers';
let searchQuery = '';
let favorites = JSON.parse(localStorage.getItem('r6_favorites') || '[]');
let userDpi = parseInt(localStorage.getItem('r6_dpi') || '400', 10);
let selectedOperator = null;
let selectedWeapon = null;

// DOM Elements
const grid = document.getElementById('operators-grid');
const searchInput = document.getElementById('search-input');
const tabBtns = document.querySelectorAll('.tab-btn');
const intensitySlider = document.getElementById('intensity');
const intensityVal = document.getElementById('intensity-val');

// Python Bridge Connection
window.addEventListener('pywebviewready', function () {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');

    // Poll the backend every 500ms to safely check CapsLock status
    setInterval(() => {
        pywebview.api.get_caps_state().then(isOn => {
            if (isOn) {
                indicator.classList.remove('idle');
                indicator.classList.add('active');
                text.innerText = "ON";
            } else {
                indicator.classList.remove('active');
                indicator.classList.add('idle');
                text.innerText = "OFF";
            }
        }).catch(err => console.error("[PyWebView API Error]", err));
    }, 500);

    // Send initial DPI multiplier to backend just to be safe
    const startVal = parseFloat(intensitySlider.value).toFixed(2);
    pywebview.api.set_multiplier(parseFloat(startVal));
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Sort alpha
    operatorData.sort((a, b) => a.name.localeCompare(b.name));

    renderGrid();

    // Search Listener
    searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase();
        renderGrid();
    });

    // Tab Listeners
    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            tabBtns.forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            currentTab = e.currentTarget.dataset.tab;
            renderGrid();
        });
    });

    // Intensity Slider
    intensitySlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value).toFixed(2);
        intensityVal.textContent = val + 'x';
        // Send to Python
        if (window.pywebview) {
            pywebview.api.set_multiplier(parseFloat(val));
        }
    });

    // Remove the old manual timeout check here. We will use the proper pywebviewready event instead.


    // DPI Input Listeners
    const dpiInput = document.getElementById('dpi-input');
    if (dpiInput) {
        dpiInput.value = userDpi;
        dpiInput.addEventListener('change', (e) => {
            userDpi = parseInt(e.target.value, 10) || 400;
            localStorage.setItem('r6_dpi', userDpi);
            // Re-trigger selection to apply new math
            if (selectedOperator && selectedWeapon) {
                selectWeapon(selectedOperator, selectedWeapon);
            }
        });
    }
});

function toggleFavorite(opName) {
    if (favorites.includes(opName)) {
        favorites = favorites.filter(f => f !== opName);
    } else {
        favorites.push(opName);
    }
    localStorage.setItem('r6_favorites', JSON.stringify(favorites));
    renderGrid();
}

function selectWeapon(op, weapon) {
    selectedOperator = op;
    selectedWeapon = weapon;

    const cleanName = op.name.toLowerCase().replace(/[^a-z0-9]/g, '');
    const badgeUrl = `https://trackercdn.com/cdn/r6.tracker.network/operators/badges/${cleanName}.png`;

    // Update UI Sidebar
    const avatarEl = document.getElementById('selected-op-initials');
    avatarEl.innerHTML = `<img src="${badgeUrl}" onerror="this.onerror=null; this.outerHTML='${op.name.substring(0, 2).toUpperCase()}'" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%; border: 2px solid var(--accent);"/>`;
    avatarEl.style.background = 'transparent';

    document.getElementById('selected-name').innerText = op.name;
    document.getElementById('selected-weapon').innerText = weapon.name;
    document.getElementById('val-x').innerText = weapon.x;
    document.getElementById('val-y').innerText = weapon.y;

    // Apply visual styling to list
    document.querySelectorAll('.weapon-btn').forEach(btn => btn.classList.remove('selected'));
    const activeBtn = document.getElementById(`wpn-${op.name}-${weapon.name}`);
    if (activeBtn) activeBtn.classList.add('selected');

    // Trigger Python Backend with DPI Math
    // Target base is 400 DPI. If running 800 DPI, we drop values by half (x 0.5)
    const dpiMultiplier = 400 / userDpi;
    const scaledX = weapon.x * dpiMultiplier;
    const scaledY = weapon.y * dpiMultiplier;

    if (window.pywebview) {
        pywebview.api.set_recoil(scaledX, scaledY);
    } else {
        console.log(`[DEV Mock] Selected ${op.name} - ${weapon.name} | Base X:${weapon.x} Y:${weapon.y} | Scaled X:${scaledX} Y:${scaledY}`);
    }
}

function renderGrid() {
    grid.innerHTML = '';

    let filtered = operatorData;

    // Filter based on Tab
    if (currentTab === 'attackers') {
        filtered = filtered.filter(op => op.role === 'Attacker');
    } else if (currentTab === 'defenders') {
        filtered = filtered.filter(op => op.role === 'Defender');
    } else if (currentTab === 'favorites') {
        filtered = filtered.filter(op => favorites.includes(op.name));
    }

    // Filter based on Search (match op name or weapon name)
    if (searchQuery) {
        filtered = filtered.filter(op =>
            op.name.toLowerCase().includes(searchQuery) ||
            op.weapons.some(w => w.name.toLowerCase().includes(searchQuery))
        );
    }

    // Sort Favorites to the top if we are inside Attacker/Defender tabs
    if (currentTab !== 'favorites') {
        filtered.sort((a, b) => {
            const aFav = favorites.includes(a.name) ? 1 : 0;
            const bFav = favorites.includes(b.name) ? 1 : 0;
            return bFav - aFav;
        });
    }

    filtered.forEach(op => {
        const isFav = favorites.includes(op.name);

        // Group Element
        const groupEl = document.createElement('div');
        groupEl.className = 'op-group';

        // Header
        const initials = op.name.substring(0, 2).toUpperCase();
        // Attacker Red, Defender Blue
        const roleColor = op.role === 'Attacker' ? 'var(--attacker)' : 'var(--defender)';

        const cleanName = op.name.toLowerCase().replace(/[^a-z0-9]/g, '');
        const badgeUrl = `https://trackercdn.com/cdn/r6.tracker.network/operators/badges/${cleanName}.png`;

        let weaponsHtml = op.weapons.map(wpn => {
            const isSelected = selectedOperator?.name === op.name && selectedWeapon?.name === wpn.name;
            let cleanWpn = wpn.name.toLowerCase().replace(/[^a-z0-9]/g, '');
            const wpnIconUrl = `https://trackercdn.com/cdn/r6.tracker.network/weapons/${cleanWpn}.png`;
            return `
        <button id="wpn-${op.name}-${wpn.name}" class="weapon-btn ${isSelected ? 'selected' : ''}" onclick="selectWeapon(${JSON.stringify(op).replace(/"/g, '&quot;')}, ${JSON.stringify(wpn).replace(/"/g, '&quot;')})">
          <div style="display: flex; align-items: center; gap: 8px;">
            <img src="${wpnIconUrl}" onerror="this.style.display='none'" style="width: 28px; height: 14px; object-fit: contain; filter: drop-shadow(0 1px 1px rgba(0,0,0,0.8));" />
            <span class="weapon-name">${wpn.name}</span>
          </div>
          <span class="weapon-stats">X${wpn.x} Y${wpn.y}</span>
        </button>
      `;
        }).join('');

        groupEl.style.borderTop = `2px solid ${roleColor}`;

        groupEl.innerHTML = `
      <div class="op-header">
        <div class="op-info">
          <div class="small-avatar" style="overflow: hidden; position: relative; background: var(--bg-dark);">
            <img src="${badgeUrl}" alt="${initials}" onerror="this.onerror=null; this.outerHTML='<span style=\\'color: var(--text-muted); font-weight: 600;\\'>${initials}</span>';" style="position: absolute; width: 100%; height: 100%; object-fit: cover; transform: scale(1.15); opacity: 0.9;"/>
          </div>
          <h3 style="font-size: 14px; font-weight: 600; color: var(--text-main);">${op.name}</h3>
        </div>
        <button class="fav-btn ${isFav ? 'active' : ''}" onclick="toggleFavorite('${op.name}')">
          <span class="material-icons-outlined">${isFav ? 'star' : 'star_border'}</span>
        </button>
      </div>
      <div class="weapons-list">
        ${weaponsHtml}
      </div>
    `;

        grid.appendChild(groupEl);
    });
}
