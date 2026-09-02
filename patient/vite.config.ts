import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // The kiosk talks to the server on 8000. Proxying keeps the browser on one
    // origin, which avoids CORS entirely and means the camera and microphone
    // permissions are granted once for the whole terminal.
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
