const fs = require('fs');
const path = require('path');

// =========================================================================
// 💡 AUTO-LOADER DE VARIABLES DE ENTORNO (variables.sh)
// =========================================================================
function loadEnvFromSh() {
  try {
    // Apuntamos al archivo variables.sh en la carpeta raíz (un nivel arriba)
    const envPath = path.resolve(__dirname, '../variables.sh');
    const envFile = fs.readFileSync(envPath, 'utf8');

    const lines = envFile.split('\n');
    for (let line of lines) {
      line = line.trim();

      // Ignorar líneas vacías y comentarios
      if (!line || line.startsWith('#')) continue;

      // Limpiar la palabra "export "
      if (line.startsWith('export ')) {
        line = line.replace('export ', '').trim();
      }

      // Separar por el primer signo "="
      const separatorIndex = line.indexOf('=');
      if (separatorIndex !== -1) {
        // Extraemos la llave limpiando espacios
        const key = line.substring(0, separatorIndex).trim();

        // Extraemos el valor limpiando espacios
        let value = line.substring(separatorIndex + 1).trim();

        // Limpiamos las comillas dobles o simples del valor
        if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
          value = value.substring(1, value.length - 1);
        }

        // Inyectamos en el entorno de Node.js
        process.env[key] = value;
      }
    }
    console.log("✅ variables.sh cargado automáticamente con éxito.");
  } catch (err) {
    console.error("❌ Error CRÍTICO al leer ../variables.sh:", err.message);
    process.exit(1); // Detenemos la ejecución si no consigue el archivo
  }
}

// ⚠️ IMPORTANTÍSIMO: Ejecutar el loader ANTES de importar librerías que dependan del entorno
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

const DJANGO_WEBHOOK_URL = 'http://127.0.0.1:8000/chat/webhook/process_message/';

// =========================================================================
// 🔒 MIDDLEWARE DE AUTENTICACIÓN PROTEGIDO
// =========================================================================
io.use((socket, next) => {
  try {
    const token = socket.handshake.auth.token;

    if (!token) {
      debugPrint("WS Auth: Token no provisto");
      return next(new Error("Autenticación denegada: Token no provisto"));
    }

    // Desciframos
    const decoded = jwt.verify(token, JWT_SECRET);
    socket.user_id = decoded.user_id;
    next();
  } catch (err) {
    console.error("❌ Error descifrando JWT en el handshake:", err.message);
    return next(new Error("Autenticación denegada: Token inválido o expirado"));
  }
});

// =========================================================================
// 🚀 TRACKING DE PRESENCIA EN TIEMPO REAL (In-Memory Maps)
// =========================================================================
const activeChats = new Map(); // Llave: socket.id, Valor: order_id
const onlineUsers = new Map(); // Llave: user_id,   Valor: set de socket.ids

io.on('connection', (socket) => {
  // Registramos al usuario en el mapa global de conexiones online
  if (!onlineUsers.has(String(socket.user_id))) {
    onlineUsers.set(String(socket.user_id), new Set());
  }
  onlineUsers.get(String(socket.user_id)).add(socket.id);

  // Al entrar a una sala específica
  socket.on('join_chat', async (data) => {
    const orderId = String(data.order_id);
    if (!orderId) return;

    socket.join(`order_${orderId}`);
    activeChats.set(socket.id, orderId);

    console.log(`✅ Usuario [ID: ${socket.user_id}] entró a la sala de la orden: ${orderId}`);

    // Informamos a la sala que el usuario está "online" dentro del chat
    socket.to(`order_${orderId}`).emit('presence_change', { user_id: socket.user_id, status: 'online' });

    // Verificamos si la contraparte ya estaba adentro para avisarle al usuario que entre como 'online'
    const room = io.sockets.adapter.rooms.get(`order_${orderId}`);
    if (room && room.size > 1) {
      socket.emit('presence_change', { status: 'online' });
    } else {
      socket.emit('presence_change', { status: 'offline' });
    }

    // Sincronizamos base de datos: Marcar mensajes anteriores como leídos
    try {
      // 💡 REEMPLAZAMOS LA URL QUEMADA POR UNA DINÁMICA BASADA EN LA QUE SÍ FUNCIONA
      const markReadUrl = DJANGO_WEBHOOK_URL.replace('process_message/', 'mark_room_as_read/');

      await axios.post(markReadUrl, {
        order_id: orderId,
        user_id: socket.user_id
      }, { headers: { 'X-Microservice-Token': INTERNAL_SECRET } });

      socket.to(`order_${orderId}`).emit('room_read_receipt', { order_id: orderId });
    } catch (err) {
      console.error("❌ Error sincronizando lecturas:", err.message);
    }
  });

  // Evento de Escritura (WhatsApp style typing indicator)
  socket.on('typing', (data) => {
    const orderId = activeChats.get(socket.id);
    if (orderId) {
      socket.to(`order_${orderId}`).emit('typing_status', {
        user_id: socket.user_id,
        isTyping: data.isTyping
      });
    }
  });

  // Procesador maestro de mensajes (Agrega soporte multimedia)
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
        // Retransmitimos el JSON oficial de Django que incluye el id e is_read real
        io.to(roomName).emit('new_message', response.data.data);
      }
    } catch (error) {
      socket.emit('chat_error', { message: "No se pudo procesar el mensaje." });
    }
  });

  // 💡 NUEVO EVENTO PROACTIVO
  socket.on('leave_chat', (data) => {
    const orderId = String(data.order_id);
    io.to(`order_${orderId}`).emit('presence_change', { user_id: socket.user_id, status: 'offline' });
    socket.leave(`order_${orderId}`);
  });

  socket.on('disconnect', () => {
    const orderId = activeChats.get(socket.id);
    if (orderId) {
      // 💡 CAMBIAMOS socket.to POR io.to PARA EVITAR EL FALLO DE SALA ABANDONADA
      io.to(`order_${orderId}`).emit('presence_change', { user_id: socket.user_id, status: 'offline' });
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
  console.log(`🔗 Conectado a Django en: ${DJANGO_WEBHOOK_URL}`);
});