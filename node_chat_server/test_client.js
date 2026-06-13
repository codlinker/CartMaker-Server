const { io } = require("socket.io-client");
const jwt = require("jsonwebtoken");

// 💡 1. SIMULAMOS EL TOKEN DE FLUTTER
// Usamos tu llave secreta exacta para firmar un token válido
const JWT_SECRET = "A2odyYBjKJuaJv+aw9QIhYabmNXdTPo43Bm58o3onYs=";

// ⚠️ IMPORTANTE: Pon aquí el ID real de Yusbelin Torrealba o el tuyo (dueño de la tienda)
const TEST_USER_ID = "a2f751aa-15ba-4fce-9ddf-5b09f024d0d1"; 

const tokenFalsoPeroValido = jwt.sign({ user_id: TEST_USER_ID }, JWT_SECRET);

// 💡 2. NOS CONECTAMOS AL SERVIDOR DE NODE (Como lo haría Flutter)
const socket = io("http://localhost:3000", {
  auth: { token: tokenFalsoPeroValido }
});

socket.on("connect", () => {
  console.log("🟢 CONECTADO AL CHAT. Mi ID de Socket es:", socket.id);

  // Entramos a la sala de la orden 29
  console.log("Entrando a la sala de la orden 29...");
  socket.emit("join_chat", { order_id: 29 });

  // Esperamos 2 segundos y enviamos un mensaje de prueba
  setTimeout(() => {
    console.log("Enviando mensaje a Django...");
    socket.emit("send_message", {
      order_id: 29,
      text: "¡Hola! Probando los WebSockets desde la terminal 🚀"
    });
  }, 2000);
});

// 💡 3. ESCUCHAMOS LAS RESPUESTAS (Lo que pintaría los globos de chat en la UI)
socket.on("new_message", (data) => {
  console.log("\n💬 ¡NUEVO MENSAJE OFICIAL RECIBIDO!");
  console.log("-----------------------------------");
  console.log(data);
  console.log("-----------------------------------\n");
  
  // Cerramos el script después de recibir el mensaje con éxito
  setTimeout(() => process.exit(0), 1000);
});

socket.on("chat_error", (error) => {
  console.error("\n❌ ERROR RECIBIDO:", error.message);
  process.exit(1);
});

socket.on("disconnect", () => {
  console.log("🔴 Desconectado del servidor");
});