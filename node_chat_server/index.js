const fs = require('fs');
const path = require('path');

// =========================================================================
// 💡 AUTO-LOADER DE VARIABLES DE ENTORNO (variables.sh)
// =========================================================================
function loadEnvFromSh() {
  try {
    const envPath = path.resolve(__dirname, '../variables.sh');
    const envFile = fs.readFileSync(envPath, 'utf8');

    const lines = envFile.split('\n');
    for (let line of lines) {
      line = line.trim();

      if (!line || line.startsWith('#')) continue;

      if (line.startsWith('export ')) {
        line = line.replace('export ', '').trim();
      }

      const separatorIndex = line.indexOf('=');
      if (separatorIndex !== -1) {
        const key = line.substring(0, separatorIndex).trim();
        let value = line.substring(separatorIndex + 1).trim();

        if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
          value = value.substring(1, value.length - 1);
        }

        process.env[key] = value;
      }
    }
    console.log("✅ variables.sh cargado automáticamente con éxito.");
  } catch (err) {
    console.error("❌ Error CRÍTICO al leer ../variables.sh:", err.message);
    process.exit(1); 
  }
}

loadEnvFromSh();

const express = require('express');
const http = require('http');
const crypto = require('crypto');
const { Server } = require('socket.io');
const axios = require('axios');
const jwt = require('jsonwebtoken');

const app = express();
app.use(express.json());
const server = http.createServer(app);

// Configuramos Socket.io
const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  },
  allowEIO3: true
});

// Validación de la llave
const JWT_SECRET = process.env.JWT_SECRET_KEY;
const INTERNAL_SECRET = process.env.DJANGO_SECRET_KEY;

if (!JWT_SECRET || !INTERNAL_SECRET) {
  console.error("❌ CRÍTICO: Faltan llaves de seguridad en el entorno.");
  process.exit(1);
}

function isValidMicroserviceToken(headerToken) {
  if (!headerToken || typeof headerToken !== 'string') return false;
  const bufA = Buffer.from(headerToken, 'utf8');
  const bufB = Buffer.from(INTERNAL_SECRET, 'utf8');
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

// 💡 RUTAS DE WEBHOOKS
const DJANGO_BASE_URL = (process.env.DJANGO_INTERNAL_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const DJANGO_WEBHOOK_URL = `${DJANGO_BASE_URL}/chat/webhook/process_message/`;
const DJANGO_SUPPORT_WEBHOOK_URL = `${DJANGO_BASE_URL}/chat/webhook/process_support_message/`;
const DJANGO_DELIVERY_META_URL = `${DJANGO_BASE_URL}/api/v1/delivery/internal/meta/`;
const DJANGO_DELIVERY_EVENT_URL = `${DJANGO_BASE_URL}/api/v1/delivery/internal/node-event/`;
const AXIOS_WEBHOOK_TIMEOUT_MS = 5000;

// =========================================================================
// 🧠 REDIS COMPARTIDO CON DJANGO (estado de delivery en tiempo real, Fase 2+)
// =========================================================================
// Degradación elegante: si Redis está caído el chat sigue funcionando. Nunca tumba el proceso.
const REDIS_URL = process.env.REALTIME_REDIS_URL || process.env.REDIS_URL || 'redis://127.0.0.1:6379/2';
let redis = null;
let redisReady = false;

function initRedis() {
  try {
    const Redis = require('ioredis');
    redis = new Redis(REDIS_URL, {
      lazyConnect: false,
      enableOfflineQueue: false,
      maxRetriesPerRequest: 1,
      connectTimeout: 5000,
      retryStrategy: (times) => Math.min(times * 1000, 30000)
    });
    redis.on('ready', () => {
      redisReady = true;
      console.log('✅ Redis conectado para estado en tiempo real.');
    });
    redis.on('end', () => {
      redisReady = false;
    });
    redis.on('close', () => {
      redisReady = false;
    });
    redis.on('error', (err) => {
      redisReady = false;
      console.error('⚠️ Redis no disponible (el servidor sigue operando):', err && err.message);
    });
  } catch (err) {
    redis = null;
    redisReady = false;
    console.error('⚠️ No se pudo inicializar ioredis (¿falta npm install?). El servidor sigue sin Redis:', err.message);
  }
}

initRedis();

// Devuelve el cliente solo si está listo; los consumidores deben tolerar `null`.
function getRedis() {
  return redis && redisReady ? redis : null;
}

// =========================================================================
// 👷 CONTEXTO DE SESIÓN (cuenta personal / trabajador) DESDE LOS CLAIMS DEL JWT
// =========================================================================
// Los tokens sin `ctx` (emitidos antes del sistema de trabajadores) se tratan como personales.
function applyAuthContext(socket, decoded) {
  socket.user_id = decoded.user_id;
  socket.ctx = decoded.ctx === 'worker' ? 'worker' : 'personal';
  if (socket.ctx === 'worker') {
    socket.emp_id = decoded.emp_id != null ? String(decoded.emp_id) : null;
    socket.company_id = decoded.company_id != null ? String(decoded.company_id) : null;
    socket.worker_role = decoded.role || null;
  } else {
    socket.emp_id = null;
    socket.company_id = null;
    socket.worker_role = null;
  }
}

// =========================================================================
// 🔒 MIDDLEWARE DE AUTENTICACIÓN PROTEGIDO
// =========================================================================
io.use((socket, next) => {
  try {
    const token = socket.handshake.auth.token;

    if (!token) {
      console.log("WS Auth: Token no provisto");
      return next(new Error("token_missing"));
    }

    const decoded = jwt.verify(token, JWT_SECRET);
    applyAuthContext(socket, decoded);
    next();
  } catch (err) {
    console.error("❌ Error descifrando JWT en el handshake:", err.message);
    
    if (err.message.includes('expired')) {
      return next(new Error("jwt_expired"));
    }
    
    return next(new Error("invalid_token"));
  }
});

// =========================================================================
// 🚀 TRACKING DE PRESENCIA EN TIEMPO REAL (In-Memory Maps)
// =========================================================================
// 💡 activeChats mapea socket.id -> Set de nombres de sala ('order_X' o 'support_X')
const activeChats = new Map(); 
const onlineUsers = new Map(); 

function addActiveRoom(socketId, roomName) {
  if (!activeChats.has(socketId)) {
    activeChats.set(socketId, new Set());
  }
  activeChats.get(socketId).add(roomName);
}

function removeActiveRoom(socketId, roomName) {
  const rooms = activeChats.get(socketId);
  if (rooms) {
    rooms.delete(roomName);
    if (rooms.size === 0) {
      activeChats.delete(socketId);
    }
  }
}

function hasOtherUserSocketInRoom(roomName, userId, excludedSocketId) {
  const room = io.sockets.adapter.rooms.get(roomName);
  if (!room) return false;
  for (const sid of room) {
    if (sid === excludedSocketId) continue;
    const s = io.sockets.sockets.get(sid);
    if (s && String(s.user_id) === String(userId)) {
      return true;
    }
  }
  return false;
}

function hasCounterpartyInRoom(roomName, userId) {
  const room = io.sockets.adapter.rooms.get(roomName);
  if (!room) return false;
  for (const sid of room) {
    const s = io.sockets.sockets.get(sid);
    if (s && String(s.user_id) !== String(userId)) {
      return true;
    }
  }
  return false;
}

// =========================================================================
// 🔌 API INTERNA PARA DJANGO (Asignación Inteligente)
// =========================================================================

// 1. Django pregunta: "¿Quién está conectado?"
app.get('/internal/online-users', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  
  // Devolvemos el array de IDs de todos los usuarios que tienen un socket activo
  res.json({ online_users: Array.from(onlineUsers.keys()) });
});

// 2. Django ordena: "Notifica esta asignación"
app.post('/internal/emit-assignment', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const { ticket, agent_id, client_id, participant_ids } = req.body;

  // A) Avisar al Agente en su Dashboard Web
  if (agent_id) {
    io.to(`user_${agent_id}`).emit('new_ticket_assigned', ticket);
  }
  
  // B) Avisar al Cliente y Comerciante (participantes) en su App Flutter para que actualicen la lista
  const targets = new Set();
  if (client_id) targets.add(String(client_id));
  if (Array.isArray(participant_ids)) {
    participant_ids.forEach((pid) => {
      if (pid) targets.add(String(pid));
    });
  }
  targets.forEach((uid) => {
    io.to(`user_${uid}`).emit('ticket_updated', ticket);
  });
  
  // C) Avisar a la sala del chat (por si el cliente o comerciante lo tiene abierto)
  if (ticket && ticket.id != null) {
    io.to(`support_${ticket.id}`).emit('agent_assigned', ticket);
    io.to(`support_${ticket.id}`).emit('ticket_updated', ticket);
  }

  res.json({ success: true });
});

// 3. Django ordena: "Cierra el ticket y bloquea a todos con su dictamen/conclusión"
app.post('/internal/emit-ticket-closed', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const {
    ticket_id,
    reason,
    close_reason,
    resolution_note,
    client_id,
    agent_id,
    participant_ids,
    ticket
  } = req.body;

  const resolvedReason = close_reason || reason || 'Resuelto por Soporte';
  const closeEventPayload = {
    ticket_id,
    id: ticket_id,
    closed: true,
    status: 'CLOSED',
    reason: resolvedReason,
    close_reason: resolvedReason,
    resolution_outcome: resolvedReason,
    resolution_note: resolution_note || null,
    muted_client: false,
    muted_merchant: false,
    ...(ticket && typeof ticket === 'object' ? ticket : {})
  };

  // Cerrar el chat en vivo para todos en la sala
  io.to(`support_${ticket_id}`).emit('ticket_closed', closeEventPayload);
  io.to(`support_${ticket_id}`).emit('support_ticket_closed', closeEventPayload);
  io.to(`support_${ticket_id}`).emit('ticket_updated', closeEventPayload);
  
  // Actualizar las listas globales de comprador, comerciante y agente
  const targets = new Set();
  if (client_id) targets.add(String(client_id));
  if (agent_id) targets.add(String(agent_id));
  if (Array.isArray(participant_ids)) {
    participant_ids.forEach((pid) => {
      if (pid) targets.add(String(pid));
    });
  }
  targets.forEach((uid) => {
    io.to(`user_${uid}`).emit('ticket_updated', closeEventPayload);
    io.to(`user_${uid}`).emit('ticket_closed', closeEventPayload);
  });

  res.json({ success: true });
});

// 4. Django ordena: "Silencia o reactiva a un participante del ticket tripartito"
app.post('/internal/emit-support-mute', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const {
    ticket_id,
    ticket,
    target_role,
    target_user_id,
    is_muted,
    muted_client,
    muted_merchant,
    mute_reason,
    muted_user_ids,
    participant_ids,
    system_message
  } = req.body;

  const cleanMutedIds = Array.isArray(muted_user_ids) ? muted_user_ids.map((id) => String(id)) : [];
  const mutedSet = new Set(cleanMutedIds);

  // Removemos cualquier campo dependiente de sesión (is_current_user_muted / is_muted) del broadcast grupal
  let roomTicketPayload = null;
  if (ticket && typeof ticket === 'object') {
    roomTicketPayload = { ...ticket };
    delete roomTicketPayload.is_current_user_muted;
    delete roomTicketPayload.is_muted;
    roomTicketPayload.muted_client = Boolean(muted_client);
    roomTicketPayload.muted_merchant = Boolean(muted_merchant);
    roomTicketPayload.mute_reason = mute_reason || null;
    roomTicketPayload.muted_user_ids = cleanMutedIds;
  }

  const roomMutePayload = {
    ticket_id,
    id: ticket_id,
    target_role: target_role || null,
    target_user_id: target_user_id != null ? String(target_user_id) : null,
    muted_client: Boolean(muted_client),
    muted_merchant: Boolean(muted_merchant),
    mute_reason: mute_reason || null,
    muted_user_ids: cleanMutedIds,
    ticket: roomTicketPayload
  };
  if (typeof is_muted === 'boolean' && target_user_id != null) {
    roomMutePayload.target_is_muted = is_muted;
  }

  const roomName = `support_${ticket_id}`;
  io.to(roomName).emit('support_mute_status', roomMutePayload);
  io.to(roomName).emit('participant_muted', roomMutePayload);
  if (roomTicketPayload) {
    io.to(roomName).emit('ticket_updated', roomTicketPayload);
  }
  if (system_message) {
    io.to(roomName).emit('new_support_message', system_message);
  }

  if (Array.isArray(participant_ids)) {
    participant_ids.forEach((uid) => {
      if (!uid) return;
      const uidStr = String(uid);
      const isUserMuted = mutedSet.has(uidStr);
      const userTicketPayload = roomTicketPayload
        ? {
            ...roomTicketPayload,
            recipient_id: uidStr,
            is_current_user_muted: isUserMuted,
            is_muted: isUserMuted
          }
        : null;
      const userMutePayload = {
        ...roomMutePayload,
        recipient_id: uidStr,
        is_current_user_muted: isUserMuted,
        is_muted: isUserMuted,
        ticket: userTicketPayload
      };
      io.to(`user_${uidStr}`).emit('support_mute_status', userMutePayload);
      io.to(`user_${uidStr}`).emit('participant_muted', userMutePayload);
      if (userTicketPayload) {
        io.to(`user_${uidStr}`).emit('ticket_updated', userTicketPayload);
      }
    });
  }

  res.json({ success: true });
});

// 5. Django ordena: "Notifica cambio de estado de orden en tiempo real"
app.post('/internal/emit-order-status', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const {
    order_id,
    status,
    recipient_id,
    is_merchant_receiver,
    reported_by_role,
    reporter_id,
    reported_by_user_id,
    support_ticket_id,
    active_ticket_id,
    title,
    body
  } = req.body;

  const payload = {
    type: 'order_status_changed',
    order_id: order_id != null ? String(order_id) : null,
    id: order_id,
    status,
    recipient_id: recipient_id != null ? String(recipient_id) : null,
    is_merchant_receiver: Boolean(is_merchant_receiver),
    reported_by_role: reported_by_role || null,
    reporter_id: reporter_id != null ? String(reporter_id) : null,
    reported_by_user_id: reported_by_user_id != null ? String(reported_by_user_id) : null,
    support_ticket_id: support_ticket_id || null,
    active_ticket_id: active_ticket_id || null,
    title: title || null,
    body: body || null
  };

  if (recipient_id) {
    io.to(`user_${recipient_id}`).emit('order_status_changed', payload);
    io.to(`user_${recipient_id}`).emit('order_updated', payload);
  }
  if (order_id != null) {
    io.to(`order_${order_id}`).emit('order_status_changed', payload);
    io.to(`order_${order_id}`).emit('order_updated', payload);
  }

  res.json({ success: true });
});

// 6. Django ordena: "Revoca en caliente las sesiones de trabajador de este empleo"
//    (suspensión, revocación, renuncia o cambio de rol). Los sockets personales del usuario no se tocan.
app.post('/internal/emit-worker-revoked', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const { user_id, employee_id, company_id, reason } = req.body || {};
  if (!user_id || employee_id == null) {
    return res.status(400).json({ success: false, error: 'user_id y employee_id son obligatorios.' });
  }

  const userIdStr = String(user_id);
  const empIdStr = String(employee_id);
  const payload = {
    type: 'worker_access_revoked',
    user_id: userIdStr,
    employee_id: empIdStr,
    company_id: company_id != null ? String(company_id) : null,
    reason: reason || 'revoked'
  };

  let disconnected = 0;
  const socketIds = onlineUsers.has(userIdStr) ? Array.from(onlineUsers.get(userIdStr)) : [];
  socketIds.forEach((sid) => {
    const s = io.sockets.sockets.get(sid);
    if (!s) return;
    if (s.ctx === 'worker' && String(s.emp_id) === empIdStr) {
      s.emit('worker_access_revoked', payload);
      // Pequeño margen para que el evento llegue antes del cierre
      setTimeout(() => {
        try {
          s.disconnect(true);
        } catch (err) {
          console.error('⚠️ Error desconectando socket de trabajador:', err.message);
        }
      }, 250);
      disconnected += 1;
    }
  });

  console.log(`👷 Acceso de trabajador revocado [user: ${userIdStr}, emp: ${empIdStr}] -> ${disconnected} socket(s)`);
  res.json({ success: true, disconnected });
});

// =========================================================================
// 🛵 MOTOR DE DELIVERY EN TIEMPO REAL (Fases 2, 3 y 4)
//    - Dead Reckoning sobre la ruta + Filtro de Kalman 1D
//    - Salas con aislamiento estricto de privacidad (Habeas Data, Art. 28):
//      * delivery_<id>: eventos de estado para todos los participantes
//      * delivery_<id>_track_all: posiciones desde ACCEPTED (comercio + repartidor)
//      * delivery_<id>_track_client: posiciones SOLO en PICKED_UP / ARRIVING (cliente)
// =========================================================================
const DELIVERY_STATUS = {
  PENDING_RIDER: 0,
  ASSIGNED: 1,
  ACCEPTED: 2,
  AT_STORE: 3,
  PICKED_UP: 4,
  ARRIVING: 5,
  DELIVERED: 6,
  FAILED: 7,
  CANCELLED: 8
};

const EARTH_RADIUS_M = 6371000.0;
const MIN_PACE_K = 0.25;
const MAX_PACE_K = 2.5;
const MAX_IMPLIED_SPEED_MPS = 56.0; // ~200 km/h
const OFF_ROUTE_THRESHOLD_M = 40.0;
const ARRIVING_RADIUS_M = 150.0;
const LIVE_TTL_S = 6 * 3600;
const TRACE_MAXLEN = 20000;

// Cachés en memoria (respaldo si Redis no está disponible y acelerador de lecturas)
const deliveryMetaMemory = new Map(); // deliveryId -> { meta, fetchedAt }
const deliveryLiveMemory = new Map(); // deliveryId -> liveObj
const deliveryLocks = new Map();      // deliveryId -> Promise
const rerouteCooldowns = new Map();   // deliveryId -> timestamp ms
const riderSockets = new Map();       // empId -> Set(socket.id)

function haversineM(lat1, lng1, lat2, lng2) {
  const toRad = (d) => (d * Math.PI) / 180.0;
  const p1 = toRad(lat1);
  const p2 = toRad(lat2);
  const dp = p2 - p1;
  const dl = toRad(lng2 - lng1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
}

function bearingDeg(lat1, lng1, lat2, lng2) {
  const toRad = (d) => (d * Math.PI) / 180.0;
  const p1 = toRad(lat1);
  const p2 = toRad(lat2);
  const dl = toRad(lng2 - lng1);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return ((Math.atan2(y, x) * 180.0) / Math.PI + 360.0) % 360.0;
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function timeAtDistance(cumDist, cumTime, s) {
  const n = Math.min(cumDist.length, cumTime.length);
  if (n === 0) return 0.0;
  if (n === 1) return Number(cumTime[0]) || 0.0;
  const sClamped = clamp(Number(s) || 0, Number(cumDist[0]), Number(cumDist[n - 1]));
  let lo = 0;
  let hi = n - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (cumDist[mid] <= sClamped) lo = mid;
    else hi = mid;
  }
  const d0 = Number(cumDist[lo]);
  const d1 = Number(cumDist[hi]);
  const t0 = Number(cumTime[lo]);
  const t1 = Number(cumTime[hi]);
  if (d1 <= d0) return t0;
  return t0 + ((sClamped - d0) / (d1 - d0)) * (t1 - t0);
}

function pointAtDistance(points, cumDist, s) {
  const n = Math.min(points.length, cumDist.length);
  if (n === 0) return { lat: 0, lng: 0, heading: 0 };
  if (n === 1) return { lat: points[0][0], lng: points[0][1], heading: 0 };
  const sClamped = clamp(Number(s) || 0, Number(cumDist[0]), Number(cumDist[n - 1]));
  let lo = 0;
  let hi = n - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (cumDist[mid] <= sClamped) lo = mid;
    else hi = mid;
  }
  const d0 = Number(cumDist[lo]);
  const d1 = Number(cumDist[hi]);
  const [lat0, lng0] = points[lo];
  const [lat1, lng1] = points[hi];
  const frac = d1 > d0 ? clamp((sClamped - d0) / (d1 - d0), 0, 1) : 0;
  return {
    lat: lat0 + (lat1 - lat0) * frac,
    lng: lng0 + (lng1 - lng0) * frac,
    heading: bearingDeg(lat0, lng0, lat1, lng1)
  };
}

function projectOntoRoute(points, cumDist, lat, lng, hintS = null) {
  const n = Math.min(points.length, cumDist.length);
  if (n === 0) return { s: 0, dPerpM: 0, segIdx: 0, segHeading: 0 };
  if (n === 1) {
    return { s: 0, dPerpM: haversineM(lat, lng, points[0][0], points[0][1]), segIdx: 0, segHeading: 0 };
  }
  const cosLat = Math.cos((lat * Math.PI) / 180.0);
  const toXY = (pLat, pLng) => [
    ((pLng - lng) * Math.PI / 180.0) * EARTH_RADIUS_M * cosLat,
    ((pLat - lat) * Math.PI / 180.0) * EARTH_RADIUS_M
  ];

  let bestScore = Infinity;
  let bestS = 0;
  let bestPerp = Infinity;
  let bestIdx = 0;

  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = toXY(points[i][0], points[i][1]);
    const [x1, y1] = toXY(points[i + 1][0], points[i + 1][1]);
    const dx = x1 - x0;
    const dy = y1 - y0;
    const lenSq = dx * dx + dy * dy;
    const u = lenSq > 1e-6 ? clamp((-x0 * dx - y0 * dy) / lenSq, 0, 1) : 0;
    const px = x0 + u * dx;
    const py = y0 + u * dy;
    const dPerp = Math.hypot(px, py);
    const segLen = Math.max(0, Number(cumDist[i + 1]) - Number(cumDist[i]));
    const sCand = Number(cumDist[i]) + u * segLen;
    const progressPenalty = hintS != null ? Math.min(15, Math.abs(sCand - hintS) * 0.03) : 0;
    const score = dPerp + progressPenalty;
    if (score < bestScore) {
      bestScore = score;
      bestPerp = dPerp;
      bestS = sCand;
      bestIdx = i;
    }
  }

  const segHeading = bearingDeg(
    points[bestIdx][0], points[bestIdx][1],
    points[bestIdx + 1][0], points[bestIdx + 1][1]
  );
  return { s: bestS, dPerpM: bestPerp, segIdx: bestIdx, segHeading };
}

function expectedSpeedAtSegment(cumDist, cumTime, segIdx) {
  if (!Array.isArray(cumDist) || !Array.isArray(cumTime) || segIdx + 1 >= cumDist.length) return 8.33;
  const dd = Number(cumDist[segIdx + 1]) - Number(cumDist[segIdx]);
  const dt = Number(cumTime[segIdx + 1]) - Number(cumTime[segIdx]);
  if (dt <= 0.05 || dd <= 0) return 8.33;
  return clamp(dd / dt, 1.0, 35.0);
}

function parseJsonSafe(raw, fallback) {
  if (!raw) return fallback;
  if (typeof raw === 'object') return raw;
  try {
    return JSON.parse(raw);
  } catch (_) {
    return fallback;
  }
}

function normalizeMeta(raw) {
  if (!raw || !raw.delivery_id) return null;
  return {
    delivery_id: Number(raw.delivery_id),
    order_id: Number(raw.order_id),
    client_user_id: String(raw.client_user_id || ''),
    merchant_user_id: String(raw.merchant_user_id || ''),
    merchant_user_ids: parseJsonSafe(raw.merchant_user_ids, raw.merchant_user_id ? [String(raw.merchant_user_id)] : []),
    rider_emp_id: raw.rider_emp_id ? String(raw.rider_emp_id) : '',
    rider_user_id: raw.rider_user_id ? String(raw.rider_user_id) : '',
    store_id: String(raw.store_id || ''),
    status: Number(raw.status || 0),
    route_version: Number(raw.route_version || 1),
    assigned_at_ms: Number(raw.assigned_at_ms || 0),
    picked_up_at_ms: Number(raw.picked_up_at_ms || 0),
    dest_lat: Number(raw.dest_lat || 0),
    dest_lng: Number(raw.dest_lng || 0),
    store_lat: Number(raw.store_lat || 0),
    store_lng: Number(raw.store_lng || 0),
    route_polyline6: String(raw.route_polyline6 || ''),
    route_points: parseJsonSafe(raw.route_points, []),
    route_cum_dist: parseJsonSafe(raw.route_cum_dist, []),
    route_cum_time: parseJsonSafe(raw.route_cum_time, []),
    route_distance_m: Number(raw.route_distance_m || 0),
    route_duration_s: Number(raw.route_duration_s || 0),
    eta_at_ms: Number(raw.eta_at_ms || 0)
  };
}

async function getDeliveryMeta(deliveryId, forceRefresh = false) {
  const key = String(deliveryId);
  const now = Date.now();
  const cached = deliveryMetaCacheGet(key, now, forceRefresh);
  if (cached) return cached;

  const r = getRedis();
  if (r) {
    try {
      const raw = await r.hgetall(`dlv:${key}:meta`);
      const parsed = normalizeMeta(raw);
      if (parsed) {
        deliveryMetaMemory.set(key, { meta: parsed, fetchedAt: now });
        return parsed;
      }
    } catch (err) {
      console.error('⚠️ Error leyendo dlv meta en Redis:', err.message);
    }
  }

  try {
    const resp = await axios.get(`${DJANGO_DELIVERY_META_URL}${encodeURIComponent(key)}/`, {
      headers: { 'X-Microservice-Token': INTERNAL_SECRET },
      timeout: 3000
    });
    const parsed = normalizeMeta(resp.data && resp.data.data);
    if (parsed) {
      deliveryMetaMemory.set(key, { meta: parsed, fetchedAt: now });
      return parsed;
    }
  } catch (err) {
    // 404 o timeout
  }
  return null;
}

function deliveryMetaCacheGet(key, now, forceRefresh) {
  if (forceRefresh) return null;
  const entry = deliveryMetaMemory.get(key);
  if (entry && now - entry.fetchedAt < 5000) {
    return entry.meta;
  }
  return null;
}

function resolveSocketDeliveryRole(socket, meta) {
  if (!socket || !meta) return null;
  const uid = String(socket.user_id || '');
  if (socket.ctx === 'worker') {
    if (meta.rider_emp_id && String(socket.emp_id) === String(meta.rider_emp_id) && uid === meta.rider_user_id) {
      return 'rider';
    }
    return null;
  }
  if (uid === meta.client_user_id) return 'client';
  if (uid === meta.merchant_user_id || (Array.isArray(meta.merchant_user_ids) && meta.merchant_user_ids.includes(uid))) {
    return 'merchant';
  }
  return null;
}

async function getLiveState(deliveryId) {
  const key = String(deliveryId);
  const r = getRedis();
  if (r) {
    try {
      const raw = await r.hgetall(`dlv:${key}:live`);
      if (raw && raw.t_a) {
        deliveryLiveMemory.set(key, raw);
        return raw;
      }
    } catch (_) {}
  }
  return deliveryLiveMemory.get(key) || null;
}

async function saveLiveState(deliveryId, stateObj, tracePoint = null) {
  const key = String(deliveryId);
  const strMap = {};
  Object.keys(stateObj).forEach((k) => {
    if (stateObj[k] !== undefined && stateObj[k] !== null) {
      strMap[k] = String(stateObj[k]);
    }
  });
  deliveryLiveMemory.set(key, strMap);

  const r = getRedis();
  if (!r) return;
  try {
    const pipe = r.pipeline();
    pipe.hset(`dlv:${key}:live`, strMap);
    pipe.expire(`dlv:${key}:live`, LIVE_TTL_S);
    if (tracePoint) {
      pipe.xadd(
        `dlv:${key}:trace`,
        'MAXLEN', '~', String(TRACE_MAXLEN), '*',
        't', String(tracePoint.t_ms),
        'ts', String(tracePoint.ts_ms),
        'lat', String(tracePoint.lat),
        'lng', String(tracePoint.lng),
        'v', String(tracePoint.speed_mps),
        'hdg', String(tracePoint.heading),
        'acc', String(tracePoint.accuracy_m),
        'src', String(tracePoint.src_code)
      );
      pipe.expire(`dlv:${key}:trace`, LIVE_TTL_S);
    }
    await pipe.exec();
  } catch (err) {
    console.error('⚠️ Error guardando estado vivo de delivery en Redis:', err.message);
  }
}

function publicAnchorFromState(state) {
  if (!state) return null;
  return {
    delivery_id: Number(state.delivery_id || 0),
    t_a: Number(state.t_a || Date.now()),
    s_a: Number(state.s_a || 0),
    k: Number(state.k || 1.0),
    sigma_a: Number(state.sigma_a || 10.0),
    sigma_rate: Number(state.sigma_rate || 1.0),
    route_version: Number(state.route_version || 1),
    mode: String(state.mode || 'route'),
    lat: Number(state.lat || 0),
    lng: Number(state.lng || 0),
    heading: Number(state.heading || 0),
    speed_mps: Number(state.speed_mps || 0),
    eta_remaining_s: Number(state.eta_remaining_s || 0),
    source: String(state.source || 'gnss_socket')
  };
}

function broadcastAnchor(deliveryId, status, anchor) {
  if (!anchor) return;
  const st = Number(status);
  // Comercio y repartidor ven el movimiento desde ACCEPTED (2..5)
  if (st >= DELIVERY_STATUS.ACCEPTED && st <= DELIVERY_STATUS.ARRIVING) {
    io.to(`delivery_${deliveryId}_track_all`).emit('delivery_anchor', anchor);
  }
  // Privacidad (Habeas Data Art. 28): el cliente SOLO recibe posición en PICKED_UP (4) y ARRIVING (5)
  if (st === DELIVERY_STATUS.PICKED_UP || st === DELIVERY_STATUS.ARRIVING) {
    io.to(`delivery_${deliveryId}_track_client`).emit('delivery_anchor', anchor);
  }
}

function notifyDjangoDeliveryEvent(payload) {
  axios.post(DJANGO_DELIVERY_EVENT_URL, payload, {
    headers: { 'X-Microservice-Token': INTERNAL_SECRET },
    timeout: 3000
  }).catch((err) => {
    console.error(`⚠️ Error enviando evento de delivery (${payload.event}) a Django:`, err.message);
  });
}

function parseRiderFixPayload(raw, defaultDeliveryId = null) {
  // 1) Formato binario compacto de 20 bytes (sección 4.3, little-endian: <IiiHHHBB)
  if (Buffer.isBuffer(raw) || raw instanceof ArrayBuffer || ArrayBuffer.isView(raw)) {
    const buf = Buffer.isBuffer(raw)
      ? raw
      : Buffer.from(raw.buffer || raw, raw.byteOffset || 0, raw.byteLength || raw.length);
    if (buf.length !== 20) return null;
    const t_ms = buf.readUInt32LE(0);
    const lat = buf.readInt32LE(4) / 1e7;
    const lng = buf.readInt32LE(8) / 1e7;
    const speed_mps = buf.readUInt16LE(12) / 100.0;
    const heading = buf.readUInt16LE(14) / 100.0;
    const accuracy_m = buf.readUInt16LE(16) / 10.0;
    const seq = buf.readUInt8(18);
    const flags = buf.readUInt8(19);
    return {
      delivery_id: defaultDeliveryId,
      t_ms,
      lat,
      lng,
      speed_mps,
      heading,
      accuracy_m,
      seq,
      flags
    };
  }
  // 2) Formato JSON equivalente (útil para pruebas o clientes web/móvil)
  if (raw && typeof raw === 'object') {
    const lat = Number(raw.lat);
    const lng = Number(raw.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return {
      delivery_id: raw.delivery_id != null ? Number(raw.delivery_id) : defaultDeliveryId,
      t_ms: Number(raw.t_ms != null ? raw.t_ms : 0),
      lat,
      lng,
      speed_mps: Math.max(0, Number(raw.speed_mps != null ? raw.speed_mps : (raw.v_cms || 0) / 100.0) || 0),
      heading: ((Number(raw.heading != null ? raw.heading : (raw.heading_cd || 0) / 100.0) || 0) % 360 + 360) % 360,
      accuracy_m: Math.max(1, Number(raw.accuracy_m != null ? raw.accuracy_m : (raw.acc_dm || 100) / 10.0) || 10),
      seq: raw.seq != null ? Number(raw.seq) & 0xFF : null,
      flags: Number(raw.flags || 0) & 0xFF
    };
  }
  return null;
}

function withDeliveryLock(deliveryId, fn) {
  const key = String(deliveryId);
  const prev = deliveryLocks.get(key) || Promise.resolve();
  const next = prev.then(fn, fn).finally(() => {
    if (deliveryLocks.get(key) === next) {
      deliveryLocks.delete(key);
    }
  });
  deliveryLocks.set(key, next);
  return next;
}

async function ingestDeliveryFix(deliveryId, fix, source = 'gnss_socket') {
  return withDeliveryLock(deliveryId, async () => {
    const meta = await getDeliveryMeta(deliveryId);
    if (!meta) return null;
    const st = Number(meta.status);
    if (st < DELIVERY_STATUS.ACCEPTED || st > DELIVERY_STATUS.ARRIVING) {
      return null;
    }
    if (Math.abs(fix.lat) > 90 || Math.abs(fix.lng) > 180 || fix.speed_mps > MAX_IMPLIED_SPEED_MPS) {
      return null;
    }

    const now = Date.now();
    const prev = await getLiveState(deliveryId);
    if (prev && source === 'gnss_socket' && fix.seq != null && prev.last_seq !== undefined && prev.last_seq !== '') {
      if (Number(prev.last_seq) === Number(fix.seq)) {
        return null; // Paquete duplicado
      }
    }

    if (prev && prev.lat != null && prev.lng != null && prev.state_t_ms) {
      const dtJumpS = Math.max(0.2, (now - Number(prev.state_t_ms)) / 1000.0);
      const jumpM = haversineM(Number(prev.lat), Number(prev.lng), fix.lat, fix.lng);
      if (dtJumpS < 30 && jumpM / dtJumpS > MAX_IMPLIED_SPEED_MPS && jumpM > 150) {
        return null; // Salto GPS físicamente imposible (> 200 km/h)
      }
    }

    const assignedAtMs = meta.assigned_at_ms || now;
    const relTms = fix.t_ms > 0 ? fix.t_ms : Math.max(0, now - assignedAtMs);
    const inTransit = st === DELIVERY_STATUS.PICKED_UP || st === DELIVERY_STATUS.ARRIVING;
    const points = Array.isArray(meta.route_points) ? meta.route_points : [];
    const cumDist = Array.isArray(meta.route_cum_dist) ? meta.route_cum_dist : [];
    const cumTime = Array.isArray(meta.route_cum_time) ? meta.route_cum_time : [];
    const hasRoute = inTransit && points.length >= 2 && cumDist.length === points.length;

    let sEst = prev ? Number(prev.s_a || 0) : 0;
    let vEst = prev ? Number(prev.v || fix.speed_mps || 0) : fix.speed_mps;
    let p00 = prev ? Number(prev.p00 || 100) : 100;
    let p01 = prev ? Number(prev.p01 || 0) : 0;
    let p11 = prev ? Number(prev.p11 || 4) : 4;
    let kEst = prev ? Number(prev.k || 1.0) : 1.0;
    let offRouteCount = prev ? Number(prev.off_route_count || 0) : 0;
    let arrivingSent = prev ? Number(prev.arriving_sent || 0) : 0;
    let mode = hasRoute ? 'route' : 'free';
    let outLat = fix.lat;
    let outLng = fix.lng;
    let outHeading = fix.heading;
    let etaRemainingS = meta.route_duration_s || 0;

    if (hasRoute) {
      const dt = prev && prev.state_t_ms ? clamp((now - Number(prev.state_t_ms)) / 1000.0, 0.05, 60.0) : 1.0;
      const sigmaAcc = 1.2;
      const q = sigmaAcc * sigmaAcc;

      // Predicción Kalman 1D: x = [s, v]
      const sPred = clamp(sEst + vEst * dt, 0, Number(cumDist[cumDist.length - 1]) || 0);
      const vPred = Math.max(0, vEst);
      const p00Pred = p00 + 2 * dt * p01 + dt * dt * p11 + 0.25 * Math.pow(dt, 4) * q;
      const p01Pred = p01 + dt * p11 + 0.5 * Math.pow(dt, 3) * q;
      const p11Pred = p11 + dt * dt * q;

      const proj = projectOntoRoute(points, cumDist, fix.lat, fix.lng, sPred);
      const rPos = Math.pow(Math.max(8.0, (fix.accuracy_m || 10.0) + 0.5 * proj.dPerpM), 2);

      // Actualización con posición proyectada s_obs
      const yPos = proj.s - sPred;
      const sInnov = p00Pred + rPos;
      const k0 = p00Pred / sInnov;
      const k1 = p01Pred / sInnov;
      sEst = clamp(sPred + k0 * yPos, 0, Number(cumDist[cumDist.length - 1]) || 0);
      vEst = clamp(vPred + k1 * yPos, 0, MAX_IMPLIED_SPEED_MPS);
      p00 = (1 - k0) * p00Pred;
      p01 = (1 - k0) * p01Pred;
      p11 = p11Pred - k1 * p01Pred;

      // Actualización con velocidad GNSS
      if (Number.isFinite(fix.speed_mps) && fix.speed_mps >= 0) {
        const rVel = 2.25;
        const yVel = fix.speed_mps - vEst;
        const sVel = p11 + rVel;
        const kv0 = p01 / sVel;
        const kv1 = p11 / sVel;
        sEst = clamp(sEst + kv0 * yVel, 0, Number(cumDist[cumDist.length - 1]) || 0);
        vEst = clamp(vEst + kv1 * yVel, 0, MAX_IMPLIED_SPEED_MPS);
        p00 = Math.max(4.0, p00 - kv0 * p01);
        p01 = (1 - kv1) * p01;
        p11 = Math.max(0.25, (1 - kv1) * p11);
      }

      const vExp = expectedSpeedAtSegment(cumDist, cumTime, proj.segIdx);
      if (vExp > 0.5 && vEst > 0.3) {
        const ratio = clamp(vEst / vExp, MIN_PACE_K, MAX_PACE_K);
        kEst = clamp(0.75 * kEst + 0.25 * ratio, MIN_PACE_K, MAX_PACE_K);
      }

      const totalTime = Number(cumTime[cumTime.length - 1] || meta.route_duration_s || 0);
      const elapsedRouteTime = timeAtDistance(cumDist, cumTime, sEst);
      etaRemainingS = Math.max(0, Math.round((totalTime - elapsedRouteTime) / Math.max(MIN_PACE_K, kEst)));

      if (proj.dPerpM > OFF_ROUTE_THRESHOLD_M) {
        offRouteCount += 1;
        if (offRouteCount >= 2) {
          mode = 'free';
          const lastReroute = rerouteCooldowns.get(String(deliveryId)) || 0;
          if (now - lastReroute > 20000) {
            rerouteCooldowns.set(String(deliveryId), now);
            notifyDjangoDeliveryEvent({
              event: 'reroute',
              delivery_id: Number(deliveryId),
              lat: fix.lat,
              lng: fix.lng
            });
          }
        }
      } else {
        offRouteCount = 0;
        mode = 'route';
        const snapped = pointAtDistance(points, cumDist, sEst);
        outLat = Number(snapped.lat.toFixed(6));
        outLng = Number(snapped.lng.toFixed(6));
        outHeading = fix.speed_mps > 1.0 ? fix.heading : Number(snapped.heading.toFixed(1));
      }
    } else if (inTransit && meta.dest_lat && meta.dest_lng) {
      const distDest = haversineM(fix.lat, fix.lng, meta.dest_lat, meta.dest_lng);
      etaRemainingS = Math.round((distDest * 1.25) / Math.max(2.5, fix.speed_mps || 7.5));
    }

    // Geocerca de llegada (< 150 m del cliente) cuando va en camino (PICKED_UP -> ARRIVING)
    if (st === DELIVERY_STATUS.PICKED_UP && !arrivingSent && meta.dest_lat && meta.dest_lng) {
      const distToDest = haversineM(fix.lat, fix.lng, meta.dest_lat, meta.dest_lng);
      if (distToDest <= ARRIVING_RADIUS_M) {
        arrivingSent = 1;
        notifyDjangoDeliveryEvent({
          event: 'arriving',
          delivery_id: Number(deliveryId)
        });
      }
    }

    const sigmaA = Number(clamp(Math.sqrt(Math.max(9.0, p00)), 3.0, 250.0).toFixed(1));
    const sigmaRate = Number((mode === 'free' ? 2.5 : clamp(Math.sqrt(Math.max(0.5, p11)), 0.8, 3.0)).toFixed(2));
    const srcCode = source === 'ble_relay' ? 2 : 0;

    const nextState = {
      delivery_id: Number(deliveryId),
      t_a: now,
      s_a: Number(sEst.toFixed(2)),
      k: Number(kEst.toFixed(3)),
      sigma_a: sigmaA,
      sigma_rate: sigmaRate,
      v: Number(vEst.toFixed(2)),
      p00: Number(p00.toFixed(3)),
      p01: Number(p01.toFixed(3)),
      p11: Number(p11.toFixed(3)),
      state_t_ms: now,
      route_version: meta.route_version,
      mode,
      lat: outLat,
      lng: outLng,
      heading: Number(outHeading.toFixed(1)),
      speed_mps: Number(fix.speed_mps.toFixed(2)),
      eta_remaining_s: etaRemainingS,
      off_route_count: offRouteCount,
      arriving_sent: arrivingSent,
      last_seq: fix.seq != null ? fix.seq : (prev && prev.last_seq != null ? prev.last_seq : ''),
      source
    };

    await saveLiveState(deliveryId, nextState, {
      t_ms: relTms,
      ts_ms: now,
      lat: fix.lat,
      lng: fix.lng,
      speed_mps: fix.speed_mps,
      heading: fix.heading,
      accuracy_m: fix.accuracy_m || 10,
      src_code: srcCode
    });

    const anchor = publicAnchorFromState(nextState);
    broadcastAnchor(deliveryId, st, anchor);
    return anchor;
  });
}

// 7. Django ordena: "Envía oferta de entrega (45 s) al repartidor"
app.post('/internal/delivery-offer', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const payload = req.body || {};
  if (payload.delivery_id != null) {
    deliveryMetaMemory.delete(String(payload.delivery_id));
  }
  if (payload.rider_user_id) {
    io.to(`user_${payload.rider_user_id}`).emit('delivery_offer', payload);
  }
  res.json({ success: true });
});

// 8. Django ordena: "Notifica cambio de estado de delivery"
app.post('/internal/delivery-status', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const payload = req.body || {};
  const deliveryId = payload.delivery_id;
  if (deliveryId != null) {
    deliveryMetaMemory.delete(String(deliveryId));
    io.to(`delivery_${deliveryId}`).emit('delivery_status_changed', payload);
  }
  if (payload.order_id != null) {
    io.to(`order_${payload.order_id}`).emit('delivery_status_changed', payload);
  }
  const userTargets = new Set();
  if (payload.client_user_id) userTargets.add(String(payload.client_user_id));
  if (payload.rider_user_id) userTargets.add(String(payload.rider_user_id));
  if (payload.previous_rider_user_id) userTargets.add(String(payload.previous_rider_user_id));
  if (Array.isArray(payload.merchant_user_ids)) {
    payload.merchant_user_ids.forEach((uid) => {
      if (uid) userTargets.add(String(uid));
    });
  }
  userTargets.forEach((uid) => {
    io.to(`user_${uid}`).emit('delivery_status_changed', payload);
  });

  if (deliveryId != null && payload.anchor) {
    broadcastAnchor(deliveryId, payload.status, payload.anchor);
  }
  if (deliveryId != null && Number(payload.status) >= DELIVERY_STATUS.DELIVERED) {
    deliveryLiveMemory.delete(String(deliveryId));
  }
  res.json({ success: true });
});

// 9. Django ordena: "Difunde nueva versión de la ruta OSRM"
app.post('/internal/delivery-route', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const payload = req.body || {};
  const deliveryId = payload.delivery_id;
  if (deliveryId != null) {
    deliveryMetaMemory.delete(String(deliveryId));
    io.to(`delivery_${deliveryId}_track_all`).emit('delivery_route_updated', payload);
    const st = Number(payload.status);
    if (st === DELIVERY_STATUS.PICKED_UP || st === DELIVERY_STATUS.ARRIVING) {
      io.to(`delivery_${deliveryId}_track_client`).emit('delivery_route_updated', payload);
    }
    if (payload.anchor) {
      broadcastAnchor(deliveryId, st, payload.anchor);
    }
  }
  res.json({ success: true });
});

// 10. Django inyecta un fix recibido por retransmisión BLE (/api/v1/delivery/relay/)
app.post('/internal/delivery-fix', async (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const body = req.body || {};
  const fix = parseRiderFixPayload(body, body.delivery_id);
  if (!fix || !fix.delivery_id) {
    return res.status(400).json({ success: false, error: 'Fix inválido.' });
  }
  try {
    const anchor = await ingestDeliveryFix(fix.delivery_id, fix, body.source || 'ble_relay');
    res.json({ success: true, anchor });
  } catch (err) {
    console.error('⚠️ Error procesando delivery-fix interno:', err.message);
    res.status(500).json({ success: false });
  }
});

// 11. Django ordena: "Difunde backfill de la traza offline al reconectar"
app.post('/internal/delivery-trace-backfill', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const { delivery_id, assigned_at_ms, points_all, points_client } = req.body || {};
  if (delivery_id != null) {
    if (Array.isArray(points_all) && points_all.length > 0) {
      io.to(`delivery_${delivery_id}_track_all`).emit('delivery_trace_backfill', {
        delivery_id,
        assigned_at_ms,
        points: points_all
      });
    }
    if (Array.isArray(points_client) && points_client.length > 0) {
      io.to(`delivery_${delivery_id}_track_client`).emit('delivery_trace_backfill', {
        delivery_id,
        assigned_at_ms,
        points: points_client
      });
    }
  }
  res.json({ success: true });
});

io.on('connection', (socket) => {
  socket.join(`user_${socket.user_id}`);
  if (!onlineUsers.has(String(socket.user_id))) {
    onlineUsers.set(String(socket.user_id), new Set());
  }
  onlineUsers.get(String(socket.user_id)).add(socket.id);

  // Si es un repartidor conectado en contexto de trabajador, marcamos presencia en Redis y avisamos al comercio
  if (socket.ctx === 'worker' && socket.worker_role === 'delivery' && socket.emp_id) {
    const empKey = String(socket.emp_id);
    if (!riderSockets.has(empKey)) {
      riderSockets.set(empKey, new Set());
    }
    riderSockets.get(empKey).add(socket.id);
    const r = getRedis();
    if (r) {
      r.set(`rider:${empKey}:online`, '1', 'EX', 90).catch(() => {});
    }
    if (socket.company_id) {
      io.to(`company_riders_${socket.company_id}`).emit('rider_presence', {
        employee_id: Number(empKey),
        online: true
      });
    }
  }

  // Permite refrescar la identidad del socket en caliente si el cliente rota su JWT sin reconectar TCP
  socket.on('refresh_auth', (data, callback) => {
    try {
      const token = data && data.token;
      if (!token) throw new Error('token_missing');
      const decoded = jwt.verify(token, JWT_SECRET);
      const oldUserId = String(socket.user_id);
      const newUserId = String(decoded.user_id);

      if (oldUserId !== newUserId) {
        socket.leave(`user_${oldUserId}`);
        if (onlineUsers.has(oldUserId)) {
          onlineUsers.get(oldUserId).delete(socket.id);
          if (onlineUsers.get(oldUserId).size === 0) {
            onlineUsers.delete(oldUserId);
          }
        }
        socket.user_id = decoded.user_id;
        socket.join(`user_${newUserId}`);
        if (!onlineUsers.has(newUserId)) {
          onlineUsers.set(newUserId, new Set());
        }
        onlineUsers.get(newUserId).add(socket.id);
      }

      // Refrescamos también el contexto de sesión (personal / trabajador) del nuevo token
      applyAuthContext(socket, decoded);

      if (typeof callback === 'function') {
        callback({
          status: 'ok',
          user_id: String(socket.user_id),
          ctx: socket.ctx,
          emp_id: socket.emp_id,
          company_id: socket.company_id,
          role: socket.worker_role
        });
      }
    } catch (err) {
      if (typeof callback === 'function') {
        callback({ status: 'error', message: err.message });
      }
    }
  });

  // =========================================================================
  // 📦 FLUJO DE ÓRDENES COMERCIALES
  // =========================================================================
  socket.on('join_chat', async (data) => {
    const orderId = data && data.order_id != null ? String(data.order_id) : '';
    if (!orderId) return;

    const roomName = `order_${orderId}`;

    try {
      const markReadUrl = DJANGO_WEBHOOK_URL.replace('process_message/', 'mark_room_as_read/');
      await axios.post(markReadUrl, {
        order_id: orderId,
        user_id: socket.user_id
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET }, timeout: AXIOS_WEBHOOK_TIMEOUT_MS });

      socket.join(roomName);
      addActiveRoom(socket.id, roomName);

      console.log(`✅ Usuario [ID: ${socket.user_id}] entró a la sala de la orden: ${orderId}`);

      socket.to(roomName).emit('presence_change', {
        order_id: orderId,
        is_support: false,
        user_id: String(socket.user_id),
        status: 'online'
      });

      if (hasCounterpartyInRoom(roomName, socket.user_id)) {
        socket.emit('presence_change', { order_id: orderId, is_support: false, status: 'online' });
      } else {
        socket.emit('presence_change', { order_id: orderId, is_support: false, status: 'offline' });
      }

      socket.to(roomName).emit('room_read_receipt', {
        order_id: orderId,
        is_support: false,
        reader_id: String(socket.user_id)
      });
    } catch (err) {
      if (err.response && (err.response.status === 403 || err.response.status === 404)) {
        socket.emit('chat_error', { order_id: orderId, message: "No tienes acceso a esta sala." });
        return;
      }
      console.error("❌ Error sincronizando lecturas de orden:", err.message);
    }
  });

  socket.on('join_dashboard', () => {
    socket.join(`agent_${socket.user_id}`);
    console.log(`🛡️ Agente [ID: ${socket.user_id}] monitoreando su dashboard`);
  });

  socket.on('send_message', async (data, callback) => {
    const {
      order_id,
      text,
      message_type,
      media_url,
      temp_id,
      metadata,
      payment_methods,
      payment_method_ids
    } = data || {};
    const roomName = `order_${order_id}`;
    const isRecipientConnected = hasCounterpartyInRoom(roomName, socket.user_id);

    try {
      const response = await axios.post(DJANGO_WEBHOOK_URL, {
        order_id: order_id,
        sender_id: socket.user_id,
        text: text,
        message_type: message_type || 'text',
        media_url: media_url || null,
        metadata: metadata || null,
        payment_methods: payment_methods || null,
        payment_method_ids: payment_method_ids || null,
        recipient_connected: isRecipientConnected,
        temp_id: temp_id || null
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET }, timeout: AXIOS_WEBHOOK_TIMEOUT_MS });

      if (response.data && response.data.success) {
        const msgPayload = {
          ...response.data.data,
          order_id: response.data.data.order_id ?? order_id,
          is_support: false
        };
        if (temp_id && !msgPayload.temp_id) {
          msgPayload.temp_id = String(temp_id);
        }

        io.to(roomName).emit('new_message', msgPayload);

        if (typeof callback === 'function') {
          callback({ status: 'ok', data: msgPayload });
        }
      } else {
        const errMsg = (response.data && response.data.error) || "No se pudo procesar el mensaje.";
        socket.emit('chat_error', { message: errMsg, order_id, temp_id: temp_id || null });
        if (typeof callback === 'function') {
          callback({ status: 'error', message: errMsg, temp_id: temp_id || null });
        }
      }
    } catch (error) {
      const errMsg = (error.response && error.response.data && error.response.data.error) || "No se pudo procesar el mensaje.";
      socket.emit('chat_error', { message: errMsg, order_id, temp_id: temp_id || null });
      if (typeof callback === 'function') {
        callback({ status: 'error', message: errMsg, temp_id: temp_id || null });
      }
    }
  });

  socket.on('leave_chat', (data) => {
    const orderId = data && data.order_id != null ? String(data.order_id) : '';
    if (!orderId) return;
    const roomName = `order_${orderId}`;
    socket.leave(roomName);
    removeActiveRoom(socket.id, roomName);
    if (!hasOtherUserSocketInRoom(roomName, socket.user_id, socket.id)) {
      io.to(roomName).emit('presence_change', {
        order_id: orderId,
        is_support: false,
        user_id: String(socket.user_id),
        status: 'offline'
      });
    }
  });

  // =========================================================================
  // 🛠️ NUEVO: FLUJO DE TICKETS DE SOPORTE
  // =========================================================================
  socket.on('join_support_chat', async (data) => {
    const ticketId = data && data.ticket_id != null ? String(data.ticket_id) : '';
    if (!ticketId) return;

    const roomName = `support_${ticketId}`;

    try {
      const markReadUrl = DJANGO_SUPPORT_WEBHOOK_URL.replace('process_support_message/', 'mark_support_room_as_read/');
      await axios.post(markReadUrl, {
        ticket_id: ticketId,
        user_id: socket.user_id
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET }, timeout: AXIOS_WEBHOOK_TIMEOUT_MS });

      socket.join(roomName);
      addActiveRoom(socket.id, roomName);

      console.log(`✅ Usuario [ID: ${socket.user_id}] entró al ticket de soporte: ${ticketId}`);

      socket.to(roomName).emit('support_presence_change', {
        ticket_id: ticketId,
        is_support: true,
        user_id: String(socket.user_id),
        status: 'online'
      });

      if (hasCounterpartyInRoom(roomName, socket.user_id)) {
        socket.emit('support_presence_change', { ticket_id: ticketId, is_support: true, status: 'online' });
      } else {
        socket.emit('support_presence_change', { ticket_id: ticketId, is_support: true, status: 'offline' });
      }

      socket.to(roomName).emit('support_room_read_receipt', {
        ticket_id: ticketId,
        is_support: true,
        reader_id: String(socket.user_id)
      });
    } catch (err) {
      if (err.response && (err.response.status === 403 || err.response.status === 404)) {
        socket.emit('chat_error', { ticket_id: ticketId, is_support: true, message: "No tienes acceso a este ticket de soporte." });
        return;
      }
      console.error("❌ Error sincronizando lecturas de soporte:", err.message);
    }
  });

  socket.on('send_support_message', async (data, callback) => {
    const { ticket_id, text, message_type, media_url, temp_id } = data || {};
    const roomName = `support_${ticket_id}`;
    const isRecipientConnected = hasCounterpartyInRoom(roomName, socket.user_id);

    try {
      const response = await axios.post(DJANGO_SUPPORT_WEBHOOK_URL, {
        ticket_id: ticket_id,
        sender_id: socket.user_id,
        text: text,
        message_type: message_type || 'text',
        media_url: media_url || null,
        recipient_connected: isRecipientConnected,
        temp_id: temp_id || null
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET }, timeout: AXIOS_WEBHOOK_TIMEOUT_MS });

      if (response.data && response.data.success) {
        const msgPayload = {
          ...response.data.data,
          ticket_id: response.data.data.ticket_id ?? ticket_id,
          is_support: Boolean(response.data.data.is_support),
          is_support_room: true
        };
        if (temp_id && !msgPayload.temp_id) {
          msgPayload.temp_id = String(temp_id);
        }

        io.to(roomName).emit('new_support_message', msgPayload);
        const recipientTargets = new Set();
        if (response.data.recipient_id) {
          recipientTargets.add(String(response.data.recipient_id));
        }
        if (Array.isArray(response.data.recipient_ids)) {
          response.data.recipient_ids.forEach((rid) => {
            if (rid) recipientTargets.add(String(rid));
          });
        }
        recipientTargets.forEach((rid) => {
          io.to(`user_${rid}`).emit('global_new_support_message', msgPayload);
        });

        if (typeof callback === 'function') {
          callback({ status: 'ok', data: msgPayload });
        }
      } else {
        const errData = response.data || {};
        const errMsg = errData.error || "No se pudo procesar el mensaje de soporte.";
        socket.emit('chat_error', {
          message: errMsg,
          code: errData.code || null,
          is_muted: Boolean(errData.is_muted),
          mute_reason: errData.mute_reason || null,
          ticket_id,
          is_support: true,
          temp_id: temp_id || null
        });
        if (typeof callback === 'function') {
          callback({
            status: 'error',
            message: errMsg,
            code: errData.code || null,
            is_muted: Boolean(errData.is_muted),
            mute_reason: errData.mute_reason || null,
            temp_id: temp_id || null
          });
        }
      }
    } catch (error) {
      const errData = (error.response && error.response.data) || {};
      const errMsg = errData.error || "No se pudo procesar el mensaje de soporte.";
      socket.emit('chat_error', {
        message: errMsg,
        code: errData.code || null,
        is_muted: Boolean(errData.is_muted),
        mute_reason: errData.mute_reason || null,
        ticket_id,
        is_support: true,
        temp_id: temp_id || null
      });
      if (typeof callback === 'function') {
        callback({
          status: 'error',
          message: errMsg,
          code: errData.code || null,
          is_muted: Boolean(errData.is_muted),
          mute_reason: errData.mute_reason || null,
          temp_id: temp_id || null
        });
      }
    }
  });

  socket.on('leave_support_chat', (data) => {
    const ticketId = data && data.ticket_id != null ? String(data.ticket_id) : '';
    if (!ticketId) return;
    const roomName = `support_${ticketId}`;
    socket.leave(roomName);
    removeActiveRoom(socket.id, roomName);
    if (!hasOtherUserSocketInRoom(roomName, socket.user_id, socket.id)) {
      io.to(roomName).emit('support_presence_change', {
        ticket_id: ticketId,
        is_support: true,
        user_id: String(socket.user_id),
        status: 'offline'
      });
    }
  });

  // =========================================================================
  // 📡 EVENTOS COMPARTIDOS
  // =========================================================================
  
  // 💡 El evento 'typing' soporta sala explícita o todas las salas activas del socket.
  socket.on('typing', (data) => {
    if (data && data.order_id != null) {
      const orderId = String(data.order_id);
      socket.to(`order_${orderId}`).emit('typing_status', {
        order_id: orderId,
        is_support: false,
        user_id: String(socket.user_id),
        isTyping: Boolean(data.isTyping)
      });
      return;
    }

    if (data && data.ticket_id != null) {
      const ticketId = String(data.ticket_id);
      socket.to(`support_${ticketId}`).emit('typing_status', {
        ticket_id: ticketId,
        is_support: true,
        user_id: String(socket.user_id),
        isTyping: Boolean(data.isTyping)
      });
      return;
    }

    const rooms = activeChats.get(socket.id);
    if (rooms) {
      for (const roomName of rooms) {
        if (roomName.startsWith('order_')) {
          const orderId = roomName.slice(6);
          socket.to(roomName).emit('typing_status', {
            order_id: orderId,
            is_support: false,
            user_id: String(socket.user_id),
            isTyping: Boolean(data && data.isTyping)
          });
        } else if (roomName.startsWith('support_')) {
          const ticketId = roomName.slice(8);
          socket.to(roomName).emit('typing_status', {
            ticket_id: ticketId,
            is_support: true,
            user_id: String(socket.user_id),
            isTyping: Boolean(data && data.isTyping)
          });
        }
      }
    }
  });

  // =========================================================================
  // 🛵 EVENTOS DE DELIVERY EN TIEMPO REAL (Dead Reckoning + Kalman 1D)
  // =========================================================================

  // Sincronización de reloj estilo NTP (sección 4.2 / 4.7)
  socket.on('time_sync', (data, callback) => {
    const tClient = data && data.t_client != null ? Number(data.t_client) : 0;
    const payload = { t_client: tClient, t_server: Date.now() };
    socket.emit('time_sync', payload);
    if (typeof callback === 'function') {
      callback(payload);
    }
  });

  // El comercio puede suscribirse a la presencia en vivo de sus repartidores
  socket.on('join_company_riders', (data, callback) => {
    const companyId = data && data.company_id ? String(data.company_id) : '';
    if (!companyId) return;
    socket.join(`company_riders_${companyId}`);
    if (typeof callback === 'function') {
      callback({ status: 'ok', company_id: companyId });
    }
  });

  // Unirse a la sala de seguimiento de una entrega (sección 4.7)
  socket.on('join_delivery', async (data, callback) => {
    const deliveryId = data && data.delivery_id != null ? Number(data.delivery_id) : null;
    if (!deliveryId) {
      const err = { status: 'error', code: 'delivery_id_required', message: 'delivery_id es obligatorio.' };
      socket.emit('delivery_error', err);
      if (typeof callback === 'function') callback(err);
      return;
    }

    const meta = await getDeliveryMeta(deliveryId);
    const role = resolveSocketDeliveryRole(socket, meta);
    if (!meta || !role) {
      const err = {
        status: 'error',
        delivery_id: deliveryId,
        code: 'not_participant',
        message: 'No tienes acceso a esta entrega.'
      };
      socket.emit('delivery_error', err);
      if (typeof callback === 'function') callback(err);
      return;
    }

    const statusRoom = `delivery_${deliveryId}`;
    const trackRoom = role === 'client' ? `delivery_${deliveryId}_track_client` : `delivery_${deliveryId}_track_all`;
    socket.join(statusRoom);
    socket.join(trackRoom);
    addActiveRoom(socket.id, statusRoom);
    addActiveRoom(socket.id, trackRoom);

    if (role === 'rider') {
      socket.active_delivery_id = deliveryId;
    }

    const live = await getLiveState(deliveryId);
    const st = Number(meta.status);
    const canSeeAnchor =
      (role === 'client' && (st === DELIVERY_STATUS.PICKED_UP || st === DELIVERY_STATUS.ARRIVING)) ||
      ((role === 'merchant' || role === 'rider') && st >= DELIVERY_STATUS.ACCEPTED && st <= DELIVERY_STATUS.ARRIVING);
    const anchor = canSeeAnchor && live ? publicAnchorFromState(live) : null;

    if (anchor) {
      socket.emit('delivery_anchor', anchor);
    }

    const response = {
      status: 'ok',
      delivery_id: deliveryId,
      role,
      delivery_status: st,
      route_version: meta.route_version,
      server_time_ms: Date.now(),
      anchor
    };
    if (typeof callback === 'function') {
      callback(response);
    }
  });

  socket.on('leave_delivery', (data, callback) => {
    const deliveryId = data && data.delivery_id != null ? Number(data.delivery_id) : socket.active_delivery_id;
    if (!deliveryId) return;
    const statusRoom = `delivery_${deliveryId}`;
    const trackAllRoom = `delivery_${deliveryId}_track_all`;
    const trackClientRoom = `delivery_${deliveryId}_track_client`;
    socket.leave(statusRoom);
    socket.leave(trackAllRoom);
    socket.leave(trackClientRoom);
    removeActiveRoom(socket.id, statusRoom);
    removeActiveRoom(socket.id, trackAllRoom);
    removeActiveRoom(socket.id, trackClientRoom);
    if (socket.active_delivery_id === deliveryId) {
      socket.active_delivery_id = null;
    }
    if (typeof callback === 'function') {
      callback({ status: 'ok', delivery_id: deliveryId });
    }
  });

  // Posición en vivo del repartidor: acepta Buffer binario de 20 B o JSON (sección 4.3)
  socket.on('rider_fix', async (raw, callback) => {
    if (socket.ctx !== 'worker' || socket.worker_role !== 'delivery' || !socket.emp_id) {
      if (typeof callback === 'function') {
        callback({ status: 'error', code: 'worker_context_required' });
      }
      return;
    }

    const fix = parseRiderFixPayload(raw, socket.active_delivery_id);
    if (!fix || !fix.delivery_id) {
      if (typeof callback === 'function') {
        callback({ status: 'error', code: 'invalid_rider_fix' });
      }
      return;
    }

    const meta = await getDeliveryMeta(fix.delivery_id);
    if (!meta || String(meta.rider_emp_id) !== String(socket.emp_id)) {
      if (typeof callback === 'function') {
        callback({ status: 'error', code: 'not_assigned_rider' });
      }
      return;
    }

    const r = getRedis();
    if (r) {
      r.set(`rider:${socket.emp_id}:online`, '1', 'EX', 90).catch(() => {});
    }

    try {
      const anchor = await ingestDeliveryFix(fix.delivery_id, fix, 'gnss_socket');
      if (typeof callback === 'function') {
        callback({ status: 'ok', anchor });
      }
    } catch (err) {
      console.error('⚠️ Error en rider_fix:', err.message);
      if (typeof callback === 'function') {
        callback({ status: 'error', message: 'internal_error' });
      }
    }
  });

  socket.on('disconnect', () => {
    if (socket.ctx === 'worker' && socket.worker_role === 'delivery' && socket.emp_id) {
      const empKey = String(socket.emp_id);
      const set = riderSockets.get(empKey);
      if (set) {
        set.delete(socket.id);
        if (set.size === 0) {
          riderSockets.delete(empKey);
          const r = getRedis();
          if (r) {
            r.del(`rider:${empKey}:online`).catch(() => {});
          }
          if (socket.company_id) {
            io.to(`company_riders_${socket.company_id}`).emit('rider_presence', {
              employee_id: Number(empKey),
              online: false
            });
          }
        }
      }
    }

    const rooms = activeChats.get(socket.id);
    if (rooms) {
      for (const roomName of rooms) {
        if (!hasOtherUserSocketInRoom(roomName, socket.user_id, socket.id)) {
          if (roomName.startsWith('order_')) {
            const orderId = roomName.slice(6);
            io.to(roomName).emit('presence_change', {
              order_id: orderId,
              is_support: false,
              user_id: String(socket.user_id),
              status: 'offline'
            });
          } else if (roomName.startsWith('support_')) {
            const ticketId = roomName.slice(8);
            io.to(roomName).emit('support_presence_change', {
              ticket_id: ticketId,
              is_support: true,
              user_id: String(socket.user_id),
              status: 'offline'
            });
          }
        }
      }
      activeChats.delete(socket.id);
    }

    if (onlineUsers.has(String(socket.user_id))) {
      onlineUsers.get(String(socket.user_id)).delete(socket.id);
      if (onlineUsers.get(String(socket.user_id)).size === 0) {
        onlineUsers.delete(String(socket.user_id));
      }
    }
    console.log(`❌ Usuario [ID: ${socket.user_id}] desconectado`);
  });
});

// =========================================================================
// 🏃 ARRANQUE DEL SERVIDOR
// =========================================================================
const PORT = process.env.PORT || 3000;

server.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Microservicio de CartMaker Chat corriendo en el puerto ${PORT}`);
});

// Expuesto para la Fase 2 (delivery en tiempo real): estado compartido con Django en Redis
module.exports = { io, app, getRedis };