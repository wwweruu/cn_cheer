import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: { input: { main: "index.html", review: "review.html", masterReview: "master-review.html", runtimeReview: "runtime-review.html", gallery: "asset-gallery.html", motionGallery:"motion-gallery.html", nativeMotionGallery:"native-motion-gallery.html" } },
  },
  server: {
    host: "127.0.0.1",
    watch: { ignored: ["**/.meshy/**", "**/assets/generated/**", "**/assets/source/**", "**/public/assets/**"] },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
