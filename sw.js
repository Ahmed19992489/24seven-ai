const CACHE_NAME = '24seven-captain-v7';
const ASSETS_TO_CACHE = [
  '/',
  '/driver.html',
  '/limousine.html',
  '/manifest.json',
  '/call-system.js',
  '/images/icon-192x192.png',
  '/images/icon-512x512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(keyList.map((key) => {
        if (key !== CACHE_NAME) return caches.delete(key);
      }));
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('supabase.co') ||
      event.request.url.includes('googleapis.com') ||
      event.request.url.includes('maps.gstatic.com')) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).catch(() => response);
    })
  );
});

// ============================================
// 🔔 Push Notifications Handler
// ============================================
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: '24Seven', body: event.data ? event.data.text() : 'اشعار جديد', type: 'general' };
  }

  const notifType = data.type || 'general';
  let title = data.title || '24Seven Limousine';
  let body = data.body || 'لديك اشعار جديد';
  let tag = '24seven-' + notifType;
  let requireInteraction = false;
  let actions = [];

  if (notifType === 'call') {
    title = 'مكالمة واردة - ' + (data.callerName || 'مجهول');
    body = (data.callerType || '') + ' يريد التحدث معك - اضغط للرد';
    requireInteraction = true;
    tag = 'incoming-call';
    actions = [{ action: 'open', title: 'فتح للرد' }];
  } else if (notifType === 'chat') {
    title = 'رسالة جديدة - ' + (data.senderName || '');
    body = data.body || 'رسالة جديدة في المحادثة';
    tag = 'chat-message';
  } else if (notifType === 'trip') {
    title = 'تحديث رحلة';
    body = data.body || 'تحديث على رحلتك';
    tag = 'trip-update';
  }

  const options = {
    body,
    icon: '/images/icon-192x192.png',
    badge: '/images/icon-192x192.png',
    tag,
    requireInteraction,
    actions,
    data: { url: data.url || '/', notifType, ...data },
    vibrate: notifType === 'call' ? [200, 100, 200, 100, 200] : [200, 100, 200],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// ============================================
// Notification Click Handler
// ============================================
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const notifData = event.notification.data || {};
  const notifType = notifData.notifType || 'general';
  let targetUrl = notifData.url || '/';
  if (notifType === 'call') targetUrl = notifData.targetPage || '/limousine.html';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(targetUrl.split('/').pop()) && 'focus' in client) {
          client.postMessage({ type: 'PUSH_CLICK', data: notifData });
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(targetUrl);
    })
  );
});
