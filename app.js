// ===================== Utilities =====================

const CACHE_NAME = 'dair-v3';
const SILENCE = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function fmt(s) {
  const m = Math.floor(s / 60);
  return m + ':' + String(Math.floor(s % 60)).padStart(2, '0');
}

// ===================== Player =====================

const audio = document.getElementById('audio');
const player = document.getElementById('player');
const playerTitle = document.getElementById('playerTitle');
const playerDesc = document.getElementById('playerDesc');
const playerBtn = document.getElementById('playerBtn');
const playerFill = document.getElementById('playerFill');
const playerTime = document.getElementById('playerTime');
const playerMini = document.getElementById('playerMini');
const playerMiniTitle = document.getElementById('playerMiniTitle');
const playerMiniBtn = document.getElementById('playerMiniBtn');
const playerMiniTime = document.getElementById('playerMiniTime');
const playerMiniFill = document.getElementById('playerMiniFill');
const ICON_PLAY = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
const ICON_PAUSE = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
let currentTrackEl = null;
let currentUrl = null;
let pendingUrl = null;
let pendingArtist = null;

function openPlayer(url, title, artist, desc) {
  playerTitle.textContent = title;
  playerDesc.textContent = desc || '';
  playerMiniTitle.textContent = title;
  player.classList.add('active');
  if (url !== currentUrl) {
    pendingUrl = url;
    pendingArtist = artist;
    playerBtn.innerHTML = ICON_PLAY;
    playerMiniBtn.innerHTML = ICON_PLAY;
  }
}

function startPlayback(url, artist) {
  currentUrl = url;
  pendingUrl = null;
  if (audio._blobUrl) { URL.revokeObjectURL(audio._blobUrl); audio._blobUrl = null; }

  // silence unlock → blob再生
  audio.src = SILENCE;
  audio.play().catch(() => {});

  caches.open(CACHE_NAME)
    .then(c => c.match(url, {ignoreSearch: true}))
    .then(r => {
      if (r) return r.blob();
      return fetch(url).then(res => res.blob());
    })
    .then(blob => {
      if (blob && blob.size > 0) {
        audio._blobUrl = URL.createObjectURL(blob);
        audio.src = audio._blobUrl;
      } else {
        audio.src = url;
      }
      return audio.play();
    })
    .catch(() => {
      audio.src = url;
      audio.load();
      audio.play().catch(() => {});
    });

  if ('mediaSession' in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: playerTitle.textContent,
      artist: artist,
      album: artist,
      artwork: [
        { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
        { src: 'icon-512.png', sizes: '512x512', type: 'image/png' }
      ]
    });
    navigator.mediaSession.setActionHandler('play', () => audio.play());
    navigator.mediaSession.setActionHandler('pause', () => audio.pause());
    navigator.mediaSession.setActionHandler('seekbackward', () => { audio.currentTime = Math.max(0, audio.currentTime - 15); });
    navigator.mediaSession.setActionHandler('seekforward', () => { audio.currentTime += 30; });
  }
}

// Overlay close (tap backdrop)
player.addEventListener('click', (e) => {
  if (e.target === player) {
    player.classList.remove('active');
    if (!audio.paused || audio.currentTime > 0) playerMini.classList.add('active');
  }
});

// Mini bar → reopen overlay
playerMini.addEventListener('click', () => {
  playerMini.classList.remove('active');
  player.classList.add('active');
});

playerBtn.addEventListener('click', () => {
  if (pendingUrl) {
    startPlayback(pendingUrl, pendingArtist);
  } else if (audio.paused) {
    audio.play();
  } else {
    audio.pause();
  }
});
playerMiniBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  if (audio.paused) { audio.play(); } else { audio.pause(); }
});
audio.addEventListener('play', () => { playerBtn.innerHTML = ICON_PAUSE; playerMiniBtn.innerHTML = ICON_PAUSE; });
audio.addEventListener('pause', () => { playerBtn.innerHTML = ICON_PLAY; playerMiniBtn.innerHTML = ICON_PLAY; });
const playerDuration = document.getElementById('playerDuration');
audio.addEventListener('timeupdate', () => {
  if (audio.duration) {
    const pct = (audio.currentTime / audio.duration * 100) + '%';
    playerFill.style.width = pct;
    playerMiniFill.style.width = pct;
    playerTime.textContent = fmt(audio.currentTime);
    playerDuration.textContent = fmt(audio.duration);
    playerMiniTime.textContent = fmt(audio.currentTime) + ' / ' + fmt(audio.duration);
    if ('mediaSession' in navigator && navigator.mediaSession.setPositionState) {
      try {
        navigator.mediaSession.setPositionState({
          duration: audio.duration, playbackRate: audio.playbackRate, position: audio.currentTime,
        });
      } catch(e) {}
    }
  }
});
function seekFromEvent(bar, e) {
  if (!audio.duration) return;
  const rect = bar.getBoundingClientRect();
  const x = (e.touches ? e.touches[0].clientX : e.clientX);
  audio.currentTime = Math.max(0, Math.min(1, (x - rect.left) / rect.width)) * audio.duration;
}

['playerProgress', 'playerMiniProgress'].forEach(id => {
  const bar = document.getElementById(id);
  bar.addEventListener('click', (e) => { e.stopPropagation(); seekFromEvent(bar, e); });
  bar.addEventListener('touchstart', (e) => { e.stopPropagation(); seekFromEvent(bar, e); }, {passive: true});
  bar.addEventListener('touchmove', (e) => { e.stopPropagation(); e.preventDefault(); seekFromEvent(bar, e); }, {passive: false});
});

// ===================== Tabs =====================

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    if (tab.dataset.tab === 'youtube') { findServer().then(() => { loadVideoAudio(); loadChannels(); }); }
  });
});

// ===================== Server Connection =====================

let MUSIC_SERVER = '';

async function findServer() {
  const saved = localStorage.getItem('va_server');
  const candidates = [
    'https://192.168.10.14:8443',
    'https://localhost:8443',
    'http://localhost:8888',
  ];
  // 前回接続成功したサーバーを優先
  if (saved && !candidates.includes(saved)) candidates.unshift(saved);
  for (const url of candidates) {
    try {
      await fetch(url + '/api/watchlist', {signal: AbortSignal.timeout(2000)});
      MUSIC_SERVER = url;
      localStorage.setItem('va_server', url);
      return;
    } catch {}
  }
}

// ===================== YouTube Audio =====================

function renderVaTracks(tracks, wl) {
  const list = document.getElementById('va-list');
  list.innerHTML = '';
  if (tracks.length === 0) {
    list.innerHTML = '<div class="va-empty">YouTube音声はありません</div>';
    return;
  }
  const chMap = {};
  wl.forEach(w => { if (w.current_file) chMap[w.current_file] = w.name; });
  tracks.sort((a, b) => b.mtime - a.mtime);
  const server = MUSIC_SERVER || localStorage.getItem('va_server') || '';

  // キャッシュ状態を一括チェック
  const trackEls = [];
  tracks.forEach(t => {
    const dur = t.duration ? Math.floor(t.duration / 60) + '分' : '';
    const fname = t.id.replace('video-audio/', '');
    const chName = chMap[fname] || '';
    const date = t.mtime ? new Date(t.mtime * 1000).toLocaleDateString('ja-JP', { month: 'long', day: 'numeric' }) : '';
    const meta = [chName, date, dur].filter(Boolean).join(' | ');
    const div = document.createElement('div');
    div.className = 'track';
    const audioUrl = server + '/video-audio/' + encodeURIComponent(fname);
    div.dataset.url = audioUrl;
    div.dataset.title = t.title;
    div.dataset.artist = chName || 'YouTube';
    div.dataset.type = 'va';
    div.innerHTML = '<div class="track-info">'
      + '<div class="track-title">' + esc(t.title) + '</div>'
      + '<div class="track-meta">' + esc(meta) + '</div>'
      + '</div>'
      + '<span class="track-cache"></span>';
    div.addEventListener('click', () => {
      if (currentTrackEl) currentTrackEl.classList.remove('playing');
      div.classList.add('playing');
      currentTrackEl = div;
      openPlayer(audioUrl, t.title, chName || 'YouTube', t.description || '');
    });
    list.appendChild(div);
    trackEls.push({ el: div, url: audioUrl });
  });

  // キャッシュチェックを1回のcaches.openでまとめて実行
  caches.open(CACHE_NAME).then(cache => {
    trackEls.forEach(({ el, url }) => {
      cache.match(url).then(r => {
        const icon = el.querySelector('.track-cache');
        if (r) {
          icon.textContent = '✓'; icon.classList.add('cached');
        } else if (MUSIC_SERVER) {
          navigator.serviceWorker?.controller?.postMessage({ type: 'CACHE_MP3', url });
        }
      });
    });
  });

  // 連続再生
  audio.onended = () => {
    if (!currentTrackEl) return;
    const next = currentTrackEl.nextElementSibling;
    if (next && next.classList.contains('track') && next.dataset.type === 'va') {
      next.click();
    }
  };
}

function renderOfflineVa() {
  const cached = localStorage.getItem('va_tracks');
  const cachedWl = localStorage.getItem('va_watchlist');
  if (cached) {
    renderVaTracks(JSON.parse(cached), cachedWl ? JSON.parse(cachedWl) : []);
  } else {
    document.getElementById('va-list').innerHTML = '<div class="va-empty">Wi-Fi接続時にデータを取得してください</div>';
  }
}

function loadVideoAudio() {
  if (!MUSIC_SERVER) {
    renderOfflineVa();
    return;
  }
  Promise.all([
    fetch(MUSIC_SERVER + '/api/video-audio').then(r => r.json()),
    fetch(MUSIC_SERVER + '/api/watchlist').then(r => r.json()).catch(() => [])
  ])
    .then(([tracks, wl]) => {
      localStorage.setItem('va_tracks', JSON.stringify(tracks));
      localStorage.setItem('va_watchlist', JSON.stringify(wl));
      localStorage.setItem('va_server', MUSIC_SERVER);
      renderVaTracks(tracks, wl);
    })
    .catch(() => {
      renderOfflineVa();
    });
}

// ===================== Service Worker =====================

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js');
}

navigator.serviceWorker?.addEventListener('message', event => {
  if (event.data.type === 'CACHE_DONE') {
    document.querySelectorAll('.track-cache').forEach(ci => {
      const trackDiv = ci.closest('.track');
      if (trackDiv && trackDiv.dataset.url === event.data.url) {
        ci.textContent = '✓'; ci.classList.add('cached');
      }
    });
    const epCache = document.querySelector('.ep-cache[data-url="' + CSS.escape(event.data.url) + '"]');
    if (epCache) {
      epCache.textContent = '✓'; epCache.style.color = '#34c759';
    }
  }
});

// ===================== Channels =====================

let watchlist = [];
let chEditMode = false;

function loadChannels() {
  if (!MUSIC_SERVER) {
    const cached = localStorage.getItem('va_watchlist');
    if (cached) { watchlist = JSON.parse(cached); renderChannels(); }
    document.getElementById('ch-edit').style.display = 'none';
    document.getElementById('ch-toggle').style.display = 'none';
    return;
  }
  fetch(MUSIC_SERVER + '/api/watchlist')
    .then(r => r.json())
    .then(wl => { watchlist = wl; renderChannels(); })
    .catch(() => {});
}

function renderChannels() {
  const list = document.getElementById('ch-list');
  list.innerHTML = '';
  watchlist.forEach(ch => {
    const div = document.createElement('div');
    div.className = 'ch-item';
    const nameSpan = document.createElement('span');
    nameSpan.className = 'ch-name';
    nameSpan.textContent = ch.name;
    div.appendChild(nameSpan);
    if (chEditMode) {
      const btn = document.createElement('button');
      btn.className = 'ch-unsub';
      btn.textContent = '解除';
      btn.addEventListener('click', () => {
        if (!confirm('「' + ch.name + '」を解除しますか？')) return;
        fetch(MUSIC_SERVER + '/api/watchlist/delete', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: ch.url })
        }).then(() => { watchlist = watchlist.filter(w => w.url !== ch.url); renderChannels(); });
      });
      div.appendChild(btn);
    }
    list.appendChild(div);
  });
}

document.getElementById('ch-edit').addEventListener('click', function() {
  chEditMode = !chEditMode;
  this.textContent = chEditMode ? '完了' : '編集';
  renderChannels();
});

document.getElementById('ch-toggle').addEventListener('click', () => {
  const s = document.getElementById('ch-search');
  s.classList.toggle('open');
  if (s.classList.contains('open')) document.getElementById('ch-query').focus();
});

let searchTimer = null;
document.getElementById('ch-query').addEventListener('input', e => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) { document.getElementById('ch-results').innerHTML = ''; return; }
  searchTimer = setTimeout(() => {
    document.getElementById('ch-results').innerHTML = '<div class="va-empty">検索中...</div>';
    fetch(MUSIC_SERVER + '/api/yt-search-channels', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q })
    })
    .then(r => r.json())
    .then(data => {
      const results = document.getElementById('ch-results');
      results.innerHTML = '';
      if (!data.results || data.results.length === 0) {
        results.innerHTML = '<div class="va-empty">見つかりません</div>';
        return;
      }
      data.results.forEach(ch => {
        const already = watchlist.some(w => w.url === ch.url || w.url === ch.url + '/videos');
        const div = document.createElement('div');
        div.className = 'ch-item';
        const nameSpan = document.createElement('span');
        nameSpan.className = 'ch-name';
        nameSpan.textContent = ch.name;
        div.appendChild(nameSpan);
        if (already) {
          const span = document.createElement('span');
          span.className = 'ch-sub subscribed';
          span.textContent = '登録済';
          div.appendChild(span);
        } else {
          const btn = document.createElement('button');
          btn.className = 'ch-add';
          btn.textContent = '登録';
          btn.addEventListener('click', function() {
            this.disabled = true; this.textContent = '...';
            fetch(MUSIC_SERVER + '/api/watchlist/add', {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ url: ch.url, name: ch.name, type: 'audio' })
            })
            .then(r => r.json())
            .then(res => {
              if (res.ok) {
                this.textContent = '登録済'; this.className = 'ch-sub subscribed';
                watchlist = res.watchlist; loadChannels();
              } else { this.textContent = res.error || 'エラー'; }
            });
          });
          div.appendChild(btn);
        }
        results.appendChild(div);
      });
    })
    .catch(() => { document.getElementById('ch-results').innerHTML = '<div class="va-empty">検索失敗</div>'; });
  }, 500);
});

// ===================== Radio Episodes =====================

fetch('feed.xml')
  .then(r => r.text())
  .then(async xml => {
    const doc = new DOMParser().parseFromString(xml, 'text/xml');
    const items = doc.querySelectorAll('item');
    const container = document.getElementById('episodes');

    const sortedItems = Array.from(items).sort((a, b) => {
      const da = new Date(a.querySelector('pubDate')?.textContent || 0);
      const db = new Date(b.querySelector('pubDate')?.textContent || 0);
      return db - da;
    });

    const cache = await caches.open(CACHE_NAME);

    for (const item of sortedItems) {
      const title = item.querySelector('title')?.textContent || '';
      const desc = item.querySelector('description')?.textContent || '';
      const url = item.querySelector('enclosure')?.getAttribute('url') || '';
      const durRaw = item.getElementsByTagNameNS('http://www.itunes.com/dtds/podcast-1.0.dtd', 'duration')[0]?.textContent || '';
      const pubDate = item.querySelector('pubDate')?.textContent || '';
      const date = new Date(pubDate).toLocaleDateString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric' });
      const durParts = durRaw.split(':').map(Number);
      const totalMin = durParts.length === 3 ? durParts[0] * 60 + durParts[1] : durParts[0] || 0;
      const dur = totalMin > 0 ? totalMin + '分' : durRaw;

      const div = document.createElement('div');
      div.className = 'track';
      div.dataset.url = url;
      div.dataset.type = 'radio';
      div.innerHTML = '<div class="track-info">'
        + '<div class="track-title">' + esc(title) + '</div>'
        + '<div class="track-meta">' + esc(date) + ' | ' + esc(dur) + ' <span class="ep-cache" data-url="' + esc(url) + '"></span></div>'
        + '</div>';
      container.appendChild(div);

      // キャッシュチェック（ループ外で開いたcacheを再利用）
      const cacheIcon = div.querySelector('.ep-cache');
      const cached = await cache.match(url);
      if (cached) {
        cacheIcon.textContent = '✓';
        cacheIcon.style.color = '#34c759';
      } else {
        navigator.serviceWorker?.controller?.postMessage({ type: 'CACHE_MP3', url: url });
      }

      div.addEventListener('click', () => {
        if (currentTrackEl) currentTrackEl.classList.remove('playing');
        div.classList.add('playing');
        currentTrackEl = div;
        openPlayer(url, title, 'CAST', desc);
      });
    }
  });
