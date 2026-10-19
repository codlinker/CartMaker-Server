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
const DJANGO_WEBHOOK_URL = 'http://127.0.0.1:8000/chat/webhook/process_message/';
const DJANGO_SUPPORT_WEBHOOK_URL = 'http://127.0.0.1:8000/chat/webhook/process_support_message/';
const AXIOS_WEBHOOK_TIMEOUT_MS = 5000;

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
    socket.user_id = decoded.user_id;
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
  const { ticket, agent_id, client_id } = req.body;

  // A) Avisar al Agente en su Dashboard Web
  io.to(`user_${agent_id}`).emit('new_ticket_assigned', ticket);
  
  // B) Avisar al Cliente en su App Flutter para que actualice la lista
  io.to(`user_${client_id}`).emit('ticket_updated', ticket);
  
  // C) Avisar a la sala del chat (por si el cliente lo tiene abierto)
  io.to(`support_${ticket.id}`).emit('agent_assigned', ticket);

  res.json({ success: true });
});

// 3. Django ordena: "Cierra el ticket y bloquea a todos"
app.post('/internal/emit-ticket-closed', (req, res) => {
  if (!isValidMicroserviceToken(req.headers['x-microservice-token'])) return res.status(403).send('Forbidden');
  const { ticket_id, reason, client_id, agent_id } = req.body;

  // Cerrar el chat
  io.to(`support_${ticket_id}`).emit('ticket_closed', { ticket_id, reason });
  
  // Actualizar las listas globales de ambos
  const payload = { id: ticket_id, closed: true, close_reason: reason };
  io.to(`user_${client_id}`).emit('ticket_updated', payload);
  io.to(`user_${agent_id}`).emit('ticket_updated', payload);

  res.json({ success: true });
});

io.on('connection', (socket) => {
  socket.join(`user_${socket.user_id}`);
  if (!onlineUsers.has(String(socket.user_id))) {
    onlineUsers.set(String(socket.user_id), new Set());
  }
  onlineUsers.get(String(socket.user_id)).add(socket.id);

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

      if (typeof callback === 'function') {
        callback({ status: 'ok', user_id: String(socket.user_id) });
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
          is_support: true
        };
        if (temp_id && !msgPayload.temp_id) {
          msgPayload.temp_id = String(temp_id);
        }

        io.to(roomName).emit('new_support_message', msgPayload);
        if (response.data.recipient_id) {
          io.to(`user_${response.data.recipient_id}`).emit('global_new_support_message', msgPayload);
        }

        if (typeof callback === 'function') {
          callback({ status: 'ok', data: msgPayload });
        }
      } else {
        const errMsg = (response.data && response.data.error) || "No se pudo procesar el mensaje de soporte.";
        socket.emit('chat_error', { message: errMsg, ticket_id, is_support: true, temp_id: temp_id || null });
        if (typeof callback === 'function') {
          callback({ status: 'error', message: errMsg, temp_id: temp_id || null });
        }
      }
    } catch (error) {
      const errMsg = (error.response && error.response.data && error.response.data.error) || "No se pudo procesar el mensaje de soporte.";
      socket.emit('chat_error', { message: errMsg, ticket_id, is_support: true, temp_id: temp_id || null });
      if (typeof callback === 'function') {
        callback({ status: 'error', message: errMsg, temp_id: temp_id || null });
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

  socket.on('disconnect', () => {
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