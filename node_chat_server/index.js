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
const { Server } = require('socket.io');
const axios = require('axios');
const jwt = require('jsonwebtoken');

const app = express();
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

// 💡 RUTAS DE WEBHOOKS
const DJANGO_WEBHOOK_URL = 'http://127.0.0.1:8000/chat/webhook/process_message/';
const DJANGO_SUPPORT_WEBHOOK_URL = 'http://127.0.0.1:8000/chat/webhook/process_support_message/';

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
// 💡 Ahora activeChats guarda el nombre COMPLETO de la sala ('order_X' o 'support_X')
const activeChats = new Map(); 
const onlineUsers = new Map(); 

io.on('connection', (socket) => {
  if (!onlineUsers.has(String(socket.user_id))) {
    onlineUsers.set(String(socket.user_id), new Set());
  }
  onlineUsers.get(String(socket.user_id)).add(socket.id);

  // =========================================================================
  // 📦 FLUJO DE ÓRDENES COMERCIALES
  // =========================================================================
  socket.on('join_chat', async (data) => {
    const orderId = String(data.order_id);
    if (!orderId) return;

    const roomName = `order_${orderId}`;
    socket.join(roomName);
    activeChats.set(socket.id, roomName);

    console.log(`✅ Usuario [ID: ${socket.user_id}] entró a la sala de la orden: ${orderId}`);

    socket.to(roomName).emit('presence_change', { user_id: socket.user_id, status: 'online' });

    const room = io.sockets.adapter.rooms.get(roomName);
    if (room && room.size > 1) {
      socket.emit('presence_change', { status: 'online' });
    } else {
      socket.emit('presence_change', { status: 'offline' });
    }

    try {
      const markReadUrl = DJANGO_WEBHOOK_URL.replace('process_message/', 'mark_room_as_read/');
      await axios.post(markReadUrl, {
        order_id: orderId,
        user_id: socket.user_id
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET } });

      socket.to(roomName).emit('room_read_receipt', { order_id: orderId });
    } catch (err) {
      console.error("❌ Error sincronizando lecturas de orden:", err.message);
    }
  });

  socket.on('send_message', async (data) => {
    const { order_id, text, message_type, media_url } = data;
    const roomName = `order_${order_id}`;
    const room = io.sockets.adapter.rooms.get(roomName);

    let isRecipientConnected = false;
    if (room) {
      for (const socketId of room) {
        const clientSocket = io.sockets.sockets.get(socketId);
        if (clientSocket && String(clientSocket.user_id) !== String(socket.user_id)) {
          isRecipientConnected = true;
          break;
        }
      }
    }

    try {
      const response = await axios.post(DJANGO_WEBHOOK_URL, {
        order_id: order_id,
        sender_id: socket.user_id,
        text: text,
        message_type: message_type || 'text',
        media_url: media_url || null,
        recipient_connected: isRecipientConnected
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET } });

      if (response.data.success) {
        io.to(roomName).emit('new_message', response.data.data);
      }
    } catch (error) {
      socket.emit('chat_error', { message: "No se pudo procesar el mensaje." });
    }
  });

  socket.on('leave_chat', (data) => {
    const roomName = `order_${data.order_id}`;
    io.to(roomName).emit('presence_change', { user_id: socket.user_id, status: 'offline' });
    socket.leave(roomName);
  });

  // =========================================================================
  // 🛠️ NUEVO: FLUJO DE TICKETS DE SOPORTE
  // =========================================================================
  socket.on('join_support_chat', async (data) => {
    const ticketId = String(data.ticket_id);
    if (!ticketId) return;

    const roomName = `support_${ticketId}`;
    socket.join(roomName);
    activeChats.set(socket.id, roomName);

    console.log(`✅ Usuario [ID: ${socket.user_id}] entró al ticket de soporte: ${ticketId}`);

    socket.to(roomName).emit('support_presence_change', { user_id: socket.user_id, status: 'online' });

    const room = io.sockets.adapter.rooms.get(roomName);
    if (room && room.size > 1) {
      socket.emit('support_presence_change', { status: 'online' });
    } else {
      socket.emit('support_presence_change', { status: 'offline' });
    }

    try {
      const markReadUrl = DJANGO_SUPPORT_WEBHOOK_URL.replace('process_support_message/', 'mark_support_room_as_read/');
      await axios.post(markReadUrl, {
        ticket_id: ticketId,
        user_id: socket.user_id
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET } });

      socket.to(roomName).emit('support_room_read_receipt', { ticket_id: ticketId });
    } catch (err) {
      console.error("❌ Error sincronizando lecturas de soporte:", err.message);
    }
  });

  socket.on('send_support_message', async (data) => {
    const { ticket_id, text, message_type, media_url } = data;
    const roomName = `support_${ticket_id}`;
    const room = io.sockets.adapter.rooms.get(roomName);

    let isRecipientConnected = false;
    if (room) {
      for (const socketId of room) {
        const clientSocket = io.sockets.sockets.get(socketId);
        if (clientSocket && String(clientSocket.user_id) !== String(socket.user_id)) {
          isRecipientConnected = true;
          break;
        }
      }
    }

    try {
      const response = await axios.post(DJANGO_SUPPORT_WEBHOOK_URL, {
        ticket_id: ticket_id,
        sender_id: socket.user_id,
        text: text,
        message_type: message_type || 'text',
        media_url: media_url || null,
        recipient_connected: isRecipientConnected
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET } });

      if (response.data.success) {
        io.to(roomName).emit('new_support_message', response.data.data);
      }
    } catch (error) {
      socket.emit('chat_error', { message: "No se pudo procesar el mensaje de soporte." });
    }
  });

  socket.on('leave_support_chat', (data) => {
    const roomName = `support_${data.ticket_id}`;
    io.to(roomName).emit('support_presence_change', { user_id: socket.user_id, status: 'offline' });
    socket.leave(roomName);
  });

  // =========================================================================
  // 📡 EVENTOS COMPARTIDOS
  // =========================================================================
  
  // 💡 El evento 'typing' ahora es genérico. Se envía a la sala en la que esté el socket.
  socket.on('typing', (data) => {
    const roomName = activeChats.get(socket.id);
    if (roomName) {
      socket.to(roomName).emit('typing_status', {
        user_id: socket.user_id,
        isTyping: data.isTyping
      });
    }
  });

  socket.on('disconnect', () => {
    const roomName = activeChats.get(socket.id);
    if (roomName) {
      // 💡 Identificamos qué tipo de sala estaba abandonando para emitir el evento correcto
      if (roomName.startsWith('order_')) {
        io.to(roomName).emit('presence_change', { user_id: socket.user_id, status: 'offline' });
      } else if (roomName.startsWith('support_')) {
        io.to(roomName).emit('support_presence_change', { user_id: socket.user_id, status: 'offline' });
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